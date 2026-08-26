import AppKit
import ApplicationServices

private let codexBundleIdentifier = "com.openai.codex"
private let clockwiseKeyCode: CGKeyCode = 90 // F20
private let counterClockwiseKeyCode: CGKeyCode = 80 // F19
private let requiredModifiers: CGEventFlags = [.maskCommand, .maskControl, .maskAlternate]

private func value<T>(_ element: AXUIElement, _ attribute: CFString) -> T? {
    var raw: CFTypeRef?
    guard AXUIElementCopyAttributeValue(element, attribute, &raw) == .success else { return nil }
    return raw as? T
}

private func frame(of element: AXUIElement) -> CGRect? {
    guard let positionValue: AXValue = value(element, kAXPositionAttribute as CFString),
          let sizeValue: AXValue = value(element, kAXSizeAttribute as CFString) else { return nil }
    var position = CGPoint.zero
    var size = CGSize.zero
    guard AXValueGetValue(positionValue, .cgPoint, &position), AXValueGetValue(sizeValue, .cgSize, &size) else {
        return nil
    }
    return CGRect(origin: position, size: size)
}

private func sidebarScrollArea(in element: AXUIElement, windowFrame: CGRect, depth: Int = 0) -> AXUIElement? {
    guard depth < 12 else { return nil }
    let role: String = value(element, kAXRoleAttribute as CFString) ?? ""
    if role == (kAXScrollAreaRole as String), let candidate = frame(of: element) {
        let isLeftSidebar = candidate.minX <= windowFrame.minX + (windowFrame.width * 0.42)
        if isLeftSidebar && candidate.height > 180 && candidate.width > 100 {
            return element
        }
    }
    let children: [AXUIElement] = value(element, kAXChildrenAttribute as CFString) ?? []
    for child in children {
        if let match = sidebarScrollArea(in: child, windowFrame: windowFrame, depth: depth + 1) {
            return match
        }
    }
    return nil
}

private func codexSidebarCenter() -> CGPoint? {
    guard let codex = NSWorkspace.shared.runningApplications.first(where: {
        $0.bundleIdentifier == codexBundleIdentifier && !$0.isTerminated
    }) else { return nil }
    let app = AXUIElementCreateApplication(codex.processIdentifier)
    let windows: [AXUIElement] = value(app, kAXWindowsAttribute as CFString) ?? []
    for window in windows {
        guard let windowFrame = frame(of: window) else { continue }
        if let sidebar = sidebarScrollArea(in: window, windowFrame: windowFrame),
           let sidebarFrame = frame(of: sidebar) {
            return CGPoint(x: sidebarFrame.midX, y: sidebarFrame.midY)
        }
        // Electron does not currently expose Codex's sidebar as an AXScrollArea.
        // Its window still provides reliable bounds, so aim directly inside the
        // left navigation pane without moving the user's physical pointer.
        return CGPoint(x: windowFrame.minX + min(180, windowFrame.width * 0.24), y: windowFrame.midY)
    }
    return nil
}

private func codexIsFrontmost() -> Bool {
    NSWorkspace.shared.frontmostApplication?.bundleIdentifier == codexBundleIdentifier
}

private func scrollSidebar(delta: Int32) {
    guard codexIsFrontmost(), let center = codexSidebarCenter(),
          let event = CGEvent(scrollWheelEvent2Source: nil, units: .line, wheelCount: 1, wheel1: delta, wheel2: 0, wheel3: 0)
    else { return }
    event.location = center
    event.post(tap: .cghidEventTap)
}

private func installEventTap() -> CFMachPort? {
    let mask = (1 << CGEventType.keyDown.rawValue)
    return CGEvent.tapCreate(
        tap: .cgSessionEventTap,
        place: .headInsertEventTap,
        options: .defaultTap,
        eventsOfInterest: CGEventMask(mask),
        callback: { _, type, event, _ in
            guard type == .keyDown,
                  codexIsFrontmost(),
                  event.flags.intersection(requiredModifiers) == requiredModifiers else { return Unmanaged.passRetained(event) }
            let keyCode = event.getIntegerValueField(.keyboardEventKeycode)
            if keyCode == Int64(counterClockwiseKeyCode) {
                scrollSidebar(delta: 2)
                return nil
            }
            if keyCode == Int64(clockwiseKeyCode) {
                scrollSidebar(delta: -2)
                return nil
            }
            return Unmanaged.passRetained(event)
        },
        userInfo: nil
    )
}

private func accessibilityTrusted(prompt: Bool) -> Bool {
    let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String: prompt] as CFDictionary
    return AXIsProcessTrustedWithOptions(options)
}

private func diagnose() {
    print("Accessibility: \(accessibilityTrusted(prompt: false) ? "granted" : "needs approval")")
    print("Codex frontmost: \(codexIsFrontmost() ? "yes" : "no")")
    if let center = codexSidebarCenter() {
        print("Sidebar target: \(Int(center.x)), \(Int(center.y))")
    } else {
        print("Sidebar target: unavailable")
    }
}

private func dumpAccessibility(_ element: AXUIElement, depth: Int = 0) {
    guard depth < 8 else { return }
    let role: String = value(element, kAXRoleAttribute as CFString) ?? "?"
    let area = frame(of: element).map { " \(Int($0.minX)),\(Int($0.minY)) \(Int($0.width))x\(Int($0.height))" } ?? ""
    print(String(repeating: "  ", count: depth) + role + area)
    let children: [AXUIElement] = value(element, kAXChildrenAttribute as CFString) ?? []
    for child in children { dumpAccessibility(child, depth: depth + 1) }
}

private func dumpCodexAccessibility() {
    guard let codex = NSWorkspace.shared.runningApplications.first(where: { $0.bundleIdentifier == codexBundleIdentifier }) else {
        print("Codex is not running")
        return
    }
    let app = AXUIElementCreateApplication(codex.processIdentifier)
    let windows: [AXUIElement] = value(app, kAXWindowsAttribute as CFString) ?? []
    for window in windows { dumpAccessibility(window) }
}

if CommandLine.arguments.contains("--diagnose") {
    diagnose()
    exit(0)
}

if CommandLine.arguments.contains("--dump-accessibility") {
    dumpCodexAccessibility()
    exit(0)
}

if CommandLine.arguments.contains("--request-accessibility") {
    _ = accessibilityTrusted(prompt: true)
    exit(0)
}

guard accessibilityTrusted(prompt: false) else {
    fputs("Kick75 sidebar controller needs macOS Accessibility permission. Run with --request-accessibility.\n", stderr)
    exit(78)
}
guard let tap = installEventTap() else {
    fputs("Kick75 sidebar controller could not install its Codex-only key listener.\n", stderr)
    exit(1)
}
let source = CFMachPortCreateRunLoopSource(kCFAllocatorDefault, tap, 0)
CFRunLoopAddSource(CFRunLoopGetCurrent(), source, .commonModes)
CGEvent.tapEnable(tap: tap, enable: true)
CFRunLoopRun()

