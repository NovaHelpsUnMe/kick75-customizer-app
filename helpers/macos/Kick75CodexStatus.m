#import <Foundation/Foundation.h>
#import <IOKit/hid/IOHIDManager.h>

static const int kKick75VendorID = 0x19F5;
static const int kKick75ProductID = 0x32D5;
static const int kKick75RawUsagePage = 0xFF60;
static const int kKick75RawUsage = 0x61;

static void captureFirstDevice(const void *value, void *context) {
    IOHIDDeviceRef *device = context;
    if (*device == NULL) *device = (IOHIDDeviceRef)value;
}

@interface Kick75CodexStatus : NSObject
@property(nonatomic) IOHIDManagerRef manager;
@property(nonatomic, strong) NSTask *reader;
@property(nonatomic, strong) NSPipe *readerOutput;
@property(nonatomic, strong) NSMutableData *buffer;
@end

@implementation Kick75CodexStatus

- (instancetype)init {
    self = [super init];
    if (!self) return nil;
    _buffer = [NSMutableData data];
    _manager = IOHIDManagerCreate(kCFAllocatorDefault, kIOHIDOptionsTypeNone);
    NSDictionary *matching = @{
        @kIOHIDVendorIDKey: @(kKick75VendorID),
        @kIOHIDProductIDKey: @(kKick75ProductID),
        @kIOHIDPrimaryUsagePageKey: @(kKick75RawUsagePage),
        @kIOHIDPrimaryUsageKey: @(kKick75RawUsage),
    };
    IOHIDManagerSetDeviceMatching(_manager, (__bridge CFDictionaryRef)matching);
    IOHIDManagerScheduleWithRunLoop(_manager, CFRunLoopGetCurrent(), kCFRunLoopCommonModes);
    if (IOHIDManagerOpen(_manager, kIOHIDOptionsTypeNone) != kIOReturnSuccess) {
        fprintf(stderr, "Kick75 status bridge cannot open the macOS HID manager.\n");
    }
    return self;
}

- (void)dealloc {
    if (_manager) {
        IOHIDManagerClose(_manager, kIOHIDOptionsTypeNone);
        CFRelease(_manager);
    }
}

- (void)start {
    NSTask *task = [[NSTask alloc] init];
    NSPipe *output = [NSPipe pipe];
    NSString *scriptPath = [[NSBundle mainBundle] pathForResource:@"codex_status" ofType:@"py"];
    if (!scriptPath) {
        fprintf(stderr, "Kick75 status reader is missing its bundled codex_status.py resource.\n");
        [self restartReader];
        return;
    }
    task.executableURL = [NSURL fileURLWithPath:@"/usr/bin/python3"];
    task.arguments = @[scriptPath, @"--stream-statuses"];
    task.standardOutput = output;
    task.standardError = [NSFileHandle fileHandleWithStandardError];
    __weak typeof(self) weakSelf = self;
    output.fileHandleForReading.readabilityHandler = ^(NSFileHandle *handle) {
        NSData *data = handle.availableData;
        if (data.length == 0) return;
        dispatch_async(dispatch_get_main_queue(), ^{ [weakSelf consume:data]; });
    };
    task.terminationHandler = ^(NSTask *_) {
        dispatch_async(dispatch_get_main_queue(), ^{
            [weakSelf restartReader];
        });
    };
    @try {
        [task launch];
        self.reader = task;
        self.readerOutput = output;
    } @catch (NSException *exception) {
        fprintf(stderr, "Kick75 status reader could not start: %s\n", exception.reason.UTF8String);
        [self restartReader];
    }
}

- (void)restartReader {
    if (self.reader.running) return;
    self.readerOutput.fileHandleForReading.readabilityHandler = nil;
    self.reader = nil;
    self.readerOutput = nil;
    [self performSelector:@selector(start) withObject:nil afterDelay:2.0];
}

- (void)consume:(NSData *)data {
    [self.buffer appendData:data];
    const uint8_t newline = '\n';
    while (true) {
        NSRange range = [self.buffer rangeOfData:[NSData dataWithBytes:&newline length:1]
                                         options:0
                                           range:NSMakeRange(0, self.buffer.length)];
        if (range.location == NSNotFound) return;
        NSData *line = [self.buffer subdataWithRange:NSMakeRange(0, range.location)];
        [self.buffer replaceBytesInRange:NSMakeRange(0, range.location + 1) withBytes:NULL length:0];
        NSString *text = [[NSString alloc] initWithData:line encoding:NSUTF8StringEncoding];
        NSArray<NSString *> *statuses = [text componentsSeparatedByString:@","];
        if (statuses.count == 4) [self sendStatuses:statuses];
    }
}

- (void)sendStatuses:(NSArray<NSString *> *)statuses {
    NSDictionary<NSString *, NSNumber *> *codes = @{
        @"off": @0, @"idle": @1, @"working": @2, @"complete": @3, @"attention": @4, @"error": @5,
    };
    uint8_t report[32] = {0};
    report[0] = 0x07; report[1] = 0x00; report[2] = 0x81;
    for (NSUInteger index = 0; index < statuses.count; index++) {
        NSNumber *code = codes[statuses[index]];
        if (!code) return;
        report[index + 3] = code.unsignedCharValue;
    }
    CFSetRef devices = IOHIDManagerCopyDevices(self.manager);
    IOHIDDeviceRef device = NULL;
    if (devices) CFSetApplyFunction(devices, captureFirstDevice, &device);
    if (!device) {
        if (devices) CFRelease(devices);
        fprintf(stderr, "Kick75 status bridge waiting: connect the keyboard by wired USB.\n");
        return;
    }
    IOReturn result = IOHIDDeviceSetReport(device, kIOHIDReportTypeOutput, 0, report, sizeof(report));
    CFRelease(devices);
    if (result != kIOReturnSuccess) {
        fprintf(stderr, "Kick75 status bridge waiting: keyboard control channel unavailable (%d).\n", result);
    }
}

@end

int main(void) {
    @autoreleasepool {
        Kick75CodexStatus *bridge = [[Kick75CodexStatus alloc] init];
        [bridge start];
        [[NSRunLoop currentRunLoop] run];
    }
    return 0;
}

