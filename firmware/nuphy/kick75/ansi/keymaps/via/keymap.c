/*
Copyright 2023 @ Nuphy <https://nuphy.com/>

This program is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 2 of the License, or
(at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

#include QMK_KEYBOARD_H
#include "via.h"
#include <lib/lib8tion/lib8tion.h>

#define CODEX_LAYER 6
#define REASONING_LAYER 7
#define CODEX_RGB_BRIGHTNESS 192
#define CODEX_RGB_SPEED 128

// This is a runtime-only VIA custom value. It deliberately does not use
// EEPROM, so status lights never alter the user's saved keyboard settings.
#define CODEX_SLOT_STATUS_VIA_VALUE 0x81
#define CODEX_STATUS_LED_ESC   0
#define CODEX_STATUS_LED_F1    1
#define CODEX_STATUS_LED_F2    2
#define CODEX_STATUS_LED_F3    3
#define CODEX_STATUS_LED_F4    4
#define CODEX_STATUS_LED_HOME  28

enum codex_status {
    CODEX_STATUS_OFF = 0,
    CODEX_STATUS_IDLE,
    CODEX_STATUS_WORKING,
    CODEX_STATUS_COMPLETE,
    CODEX_STATUS_ATTENTION,
    CODEX_STATUS_ERROR,
};

static rgb_config_t codex_previous_rgb;
static bool codex_rgb_active = false;
static uint8_t codex_slot_status[4] = {
    CODEX_STATUS_OFF,
    CODEX_STATUS_OFF,
    CODEX_STATUS_OFF,
    CODEX_STATUS_OFF,
};
// The desktop bridge cannot reliably observe a task merely being opened.
// Remember a green-task acknowledgement made with its matching Codex F-key.
static bool codex_slot_acknowledged[4] = {false, false, false, false};

static const uint16_t codex_task_keys[4] = {
    LGUI(KC_1), LGUI(KC_2), LGUI(KC_3), LGUI(KC_4)
};

static bool codex_status_is_valid(uint8_t status) {
    return status <= CODEX_STATUS_ERROR;
}

static uint8_t codex_kitt_brightness(uint8_t distance) {
    const uint8_t maximum = rgb_matrix_config.hsv.v;

    if (distance <= 3) {
        return maximum;
    }
    if (distance <= 12) {
        return scale8(maximum, 160);
    }
    if (distance <= 22) {
        return scale8(maximum, 72);
    }
    if (distance <= 34) {
        return scale8(maximum, 24);
    }
    return scale8(maximum, 6);
}

static void codex_restore_kitt_number_row(void) {
    // LEDs 14-27 are the physical ` through Backspace row. Explicitly repaint
    // it with the same scanner math after the control-key overlay so it never
    // goes dark while F5-F12 and Delete remain cyan.
    const uint8_t number_row_leds[] = {14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27};
    const uint8_t phase = scale16by8(g_rgb_timer, qadd8(rgb_matrix_config.speed, 16) >> 2);
    const uint8_t triangle = (phase & 0x80) ? (uint8_t)((255 - phase) << 1) : (uint8_t)(phase << 1);
    const uint8_t scanner_x = (uint8_t)(((uint16_t)triangle * 153) / 254);

    for (uint8_t index = 0; index < ARRAY_SIZE(number_row_leds); index++) {
        const uint8_t led = number_row_leds[index];
        const uint8_t led_x = g_led_config.point[led].x;
        const uint8_t distance = led_x > scanner_x ? led_x - scanner_x : scanner_x - led_x;
        rgb_matrix_set_color(led, codex_kitt_brightness(distance), 0, 0);
    }
}

static void codex_open_task(uint8_t slot) {
    // Opening a green task is its explicit acknowledgement. It stays assigned
    // (white) until new work starts, when the desktop bridge resets the cycle.
    if (codex_slot_status[slot] == CODEX_STATUS_COMPLETE) {
        codex_slot_acknowledged[slot] = true;
        codex_slot_status[slot] = CODEX_STATUS_IDLE;
    }
    tap_code16(codex_task_keys[slot]);
}

// VIA reserves custom channel 0 for keyboard-specific values. The status
// sender uses value 0x81 so it does not overlap VIA's built-in RGB controls.
// This runtime value is never saved to EEPROM.
void via_custom_value_command_kb(uint8_t *data, uint8_t length) {
    if (length < 7 || data[1] != id_custom_channel || data[2] != CODEX_SLOT_STATUS_VIA_VALUE) {
        data[0] = id_unhandled;
        return;
    }

    switch (data[0]) {
        case id_custom_set_value:
            if (!codex_status_is_valid(data[3]) || !codex_status_is_valid(data[4]) ||
                !codex_status_is_valid(data[5]) || !codex_status_is_valid(data[6])) {
                data[0] = id_unhandled;
                return;
            }
            for (uint8_t slot = 0; slot < 4; slot++) {
                const uint8_t requested_status = data[3 + slot];

                // A new working turn begins a new completion cycle.
                if (requested_status == CODEX_STATUS_WORKING) {
                    codex_slot_acknowledged[slot] = false;
                }

                // Once acknowledged, a finished task stays assigned-white
                // instead of returning to green on the bridge's next poll.
                codex_slot_status[slot] =
                    (requested_status == CODEX_STATUS_COMPLETE && codex_slot_acknowledged[slot])
                        ? CODEX_STATUS_IDLE
                        : requested_status;
            }
            break;
        case id_custom_get_value:
            data[3] = codex_slot_status[0];
            data[4] = codex_slot_status[1];
            data[5] = codex_slot_status[2];
            data[6] = codex_slot_status[3];
            break;
        default:
            data[0] = id_unhandled;
            break;
    }
}

bool rgb_matrix_indicators_user(void) {
    // Agent status is intentionally a Codex-layer overlay. Outside that layer,
    // the keyboard returns completely to its normal RGB behavior.
    if (!layer_state_is(CODEX_LAYER)) {
        return true;
    }

    // These keys are reserved exclusively for live Codex state. Paint them
    // black first so the KITT base effect can never sweep through them.
    const uint8_t slot_leds[4] = {
        CODEX_STATUS_LED_F1,
        CODEX_STATUS_LED_F2,
        CODEX_STATUS_LED_F3,
        CODEX_STATUS_LED_F4,
    };
    for (uint8_t slot = 0; slot < 4; slot++) {
        rgb_matrix_set_color(slot_leds[slot], 0, 0, 0);
        switch (codex_slot_status[slot]) {
            case CODEX_STATUS_IDLE:
                rgb_matrix_set_color(slot_leds[slot], 96, 96, 96);
                break;
            case CODEX_STATUS_WORKING: {
                const uint8_t brightness = 96 + scale8(sin8((uint8_t)(timer_read32() >> 4)), 159);
                rgb_matrix_set_color(slot_leds[slot], 0, scale8(brightness, 144), brightness);
                break;
            }
            case CODEX_STATUS_COMPLETE: {
                // A completed task is waiting for the user. Its green never
                // turns off, but a wide smooth two-second glow makes it easy
                // to notice without looking like a hard alert flash.
                const uint8_t brightness = 128 + scale8(sin8((uint8_t)(timer_read32() >> 3)), 127);
                rgb_matrix_set_color(slot_leds[slot], 0, brightness, scale8(brightness, 64));
                break;
            }
            case CODEX_STATUS_ATTENTION: {
                // Toggle every 125 ms: four conspicuous amber flashes/second.
                const uint8_t brightness = ((timer_read32() / 125) & 1) ? 255 : 16;
                rgb_matrix_set_color(slot_leds[slot], brightness, scale8(brightness, 96), 0);
                break;
            }
            case CODEX_STATUS_ERROR: {
                // Errors use the same rapid cadence but unmistakable pure red.
                const uint8_t brightness = ((timer_read32() / 125) & 1) ? 255 : 8;
                rgb_matrix_set_color(slot_leds[slot], brightness, 0, 0);
                break;
            }
            case CODEX_STATUS_OFF:
            default:
                break;
        }
    }

    // F5-F12 and the final top-row key before the knob are the fixed Codex
    // controls. Keep them bright electric violet so they are immediately
    // recognizable and the red KITT scanner never sweeps through them.
    const uint8_t codex_control_leds[] = {5, 6, 7, 8, 9, 10, 11, 12, 13};
    for (uint8_t control = 0; control < ARRAY_SIZE(codex_control_leds); control++) {
        rgb_matrix_set_color(codex_control_leds[control], 180, 40, 255);
    }

    codex_restore_kitt_number_row();

    // Home, Page Up, and Page Down are the shared knob-mode indicator. Keep
    // their ordinary key actions, but keep KITT off all three status LEDs.
    const uint8_t knob_status_leds[] = {CODEX_STATUS_LED_HOME, 43, 57};
    for (uint8_t indicator = 0; indicator < ARRAY_SIZE(knob_status_leds); indicator++) {
        rgb_matrix_set_color(knob_status_leds[indicator], 0, 0, 0);
    }

    if (layer_state_is(REASONING_LAYER)) {
        const uint8_t brightness = 128 + (sin8((uint8_t)(timer_read32() >> 4)) >> 1);
        for (uint8_t indicator = 0; indicator < ARRAY_SIZE(knob_status_leds); indicator++) {
            rgb_matrix_set_color(knob_status_leds[indicator], scale8(brightness, 160), 0, brightness);
        }
    } else {
        for (uint8_t indicator = 0; indicator < ARRAY_SIZE(knob_status_leds); indicator++) {
            rgb_matrix_set_color(knob_status_leds[indicator], 0, 180, 255);
        }
    }

    // Esc is the fixed exit from Codex mode. Give it a smooth, restrained red
    // pulse that remains visible above KITT without looking like an error alert.
    const uint8_t exit_brightness = 64 + scale8(sin8((uint8_t)(timer_read32() >> 4)), 96);
    rgb_matrix_set_color(CODEX_STATUS_LED_ESC, exit_brightness, 0, 0);

    return true;
}

static void codex_rgb_enable(void) {
    codex_previous_rgb = rgb_matrix_config;
    codex_rgb_active   = true;

    rgb_matrix_enable_noeeprom();
    rgb_matrix_mode_noeeprom(RGB_MATRIX_CUSTOM_kitt_scanner);
    rgb_matrix_sethsv_noeeprom(0, 255, CODEX_RGB_BRIGHTNESS);
    rgb_matrix_set_speed_noeeprom(CODEX_RGB_SPEED);
    rgb_matrix_set_flags_noeeprom(LED_FLAG_ALL);
}

static void codex_rgb_restore(void) {
    rgb_matrix_enable_noeeprom();
    rgb_matrix_mode_noeeprom(codex_previous_rgb.mode);
    rgb_matrix_sethsv_noeeprom(codex_previous_rgb.hsv.h, codex_previous_rgb.hsv.s, codex_previous_rgb.hsv.v);
    rgb_matrix_set_speed_noeeprom(codex_previous_rgb.speed);
    rgb_matrix_set_flags_noeeprom(codex_previous_rgb.flags);

    if (!codex_previous_rgb.enable) {
        rgb_matrix_disable_noeeprom();
    }

    codex_rgb_active = false;
}

layer_state_t layer_state_set_user(layer_state_t state) {
    const bool codex_layer_on = IS_LAYER_ON_STATE(state, CODEX_LAYER);

    if (codex_layer_on && !codex_rgb_active) {
        codex_rgb_enable();
    } else if (!codex_layer_on && codex_rgb_active) {
        codex_rgb_restore();
    }

    return state;
}

bool process_record_user(uint16_t keycode, keyrecord_t *record) {
    // VIA's saved dynamic keymap can override the F-key entries. In Codex
    // mode, use the physical F1-F4 positions directly so Codex always receives
    // its native "Go to Chat 1-4" shortcuts instead of brightness. Codex 26.818
    // binds these actions to Command+1 through Command+4 on macOS.
    if (record->event.key.row == 0 && record->event.key.col >= 1 && record->event.key.col <= 4 &&
        layer_state_is(CODEX_LAYER)) {
        if (record->event.pressed) {
            const uint8_t slot = record->event.key.col - 1;
            codex_open_task(slot);
        }
        return false;
    }

    // The rotary push switch is matrix row 0, column 16. Check its physical
    // position so a VIA EEPROM override cannot prevent Codex knob control.
    if (record->event.key.row == 0 && record->event.key.col == 16 &&
        (layer_state_is(CODEX_LAYER) || layer_state_is(REASONING_LAYER))) {
        if (record->event.pressed) {
            if (layer_state_is(REASONING_LAYER)) {
                layer_off(REASONING_LAYER);
            } else {
                // Cycle once using Codex's real reasoning command so its
                // compact power bar appears without opening the model picker,
                // then keep the encoder in direct reasoning-control mode.
                tap_code16(LGUI(LALT(LSFT(KC_R))));
                layer_on(REASONING_LAYER);
            }
        }
        return false;
    }

    return true;
}

const uint16_t PROGMEM keymaps[][MATRIX_ROWS][MATRIX_COLS] = {

// layer Mac
[0] = LAYOUT(
    KC_ESC, 	KC_BRID,  	KC_BRIU,  	MAC_TASK, 	MAC_SEARCH, MAC_VOICE,  MAC_DND,  	KC_MPRV,  	KC_MPLY,  	KC_MNXT, 	KC_MUTE, 	KC_VOLD, 	KC_VOLU, 	KC_DEL, 	KC_MUTE,
	KC_GRV, 	KC_1,   	KC_2,   	KC_3,  		KC_4,   	KC_5,   	KC_6,   	KC_7,   	KC_8,   	KC_9,  		KC_0,   	KC_MINS,	KC_EQL, 	KC_BSPC,	KC_HOME,
	KC_TAB, 	KC_Q,   	KC_W,   	KC_E,  		KC_R,   	KC_T,   	KC_Y,   	KC_U,   	KC_I,   	KC_O,  		KC_P,   	KC_LBRC,	KC_RBRC,	KC_BSLS,	KC_PGUP,
	KC_CAPS,	KC_A,   	KC_S,   	KC_D,  		KC_F,   	KC_G,   	KC_H,   	KC_J,   	KC_K,   	KC_L,  		KC_SCLN,	KC_QUOT, 	KC_ENT,                 KC_PGDN,
	KC_LSFT,				KC_Z,   	KC_X,   	KC_C,  		KC_V,   	KC_B,   	KC_N,   	KC_M,   	KC_COMM,	KC_DOT,		KC_SLSH,	KC_RSFT,	KC_UP,
	KC_LCTL,	KC_LOPT,	KC_LCMD,										KC_SPC, 							KC_RCMD,	MO(1),   				KC_LEFT,	KC_DOWN,    KC_RIGHT),
// layer Mac Fn
[1] = LAYOUT(
	_______, 	KC_F1,  	KC_F2,  	KC_F3, 		KC_F4,  	KC_F5,  	KC_F6,  	KC_F7,  	KC_F8,  	KC_F9, 		KC_F10, 	KC_F11, 	KC_F12, 	KC_INS,	    _______,
	_______, 	LNK_BLE1,  	LNK_BLE2,  	LNK_BLE3,  	LNK_RF,   	_______,   	_______,   	_______,   	_______,   	_______,  	_______,   	_______,	_______, 	_______,	KC_END,	
	RGB_TOG, 	_______,   	_______,   	_______,   	_______,   	_______,   	_______,   	_______,   	_______,   	_______,  	_______,   	DEV_RESET,	SLEEP_MODE, BAT_SHOW,	_______,	
	_______,	_______,   	_______,   	_______,  	_______,   	_______,   	_______,	_______,   	_______,   	_______,  	_______,	_______, 	_______,                _______,
	_______,				_______,   	_______,   	TG(CODEX_LAYER),	_______,    _______,   	_______,	MO(4), 		RGB_SPD,	RGB_SPI,	_______,	_______,	RGB_VAI,
	_______,	_______,	_______,										_______, 							_______,	MO(1),		            RGB_MOD,    RGB_VAD,	RGB_HUI),
// layer win
[2] = LAYOUT(
	KC_ESC, 	KC_F1,  	KC_F2,  	KC_F3, 		KC_F4,  	KC_F5,  	KC_F6,  	KC_F7,  	KC_F8,  	KC_F9, 		KC_F10, 	KC_F11, 	KC_F12, 	KC_DEL,    KC_MUTE,
	KC_GRV, 	KC_1,   	KC_2,   	KC_3,  		KC_4,   	KC_5,   	KC_6,   	KC_7,   	KC_8,   	KC_9,  		KC_0,   	KC_MINS,	KC_EQL, 	KC_BSPC,   KC_HOME,	    
	KC_TAB, 	KC_Q,   	KC_W,   	KC_E,  		KC_R,   	KC_T,   	KC_Y,   	KC_U,   	KC_I,   	KC_O,  		KC_P,   	KC_LBRC,	KC_RBRC,	KC_BSLS,   KC_PGUP,	
	KC_CAPS,	KC_A,   	KC_S,   	KC_D,  		KC_F,   	KC_G,   	KC_H,   	KC_J,   	KC_K,   	KC_L,  		KC_SCLN,	KC_QUOT, 	KC_ENT, 	           KC_PGDN,
	KC_LSFT,				KC_Z,   	KC_X,   	KC_C,  		KC_V,   	KC_B,   	KC_N,   	KC_M,   	KC_COMM,	KC_DOT,		KC_SLSH,	KC_RSFT,    KC_UP,						
	KC_LCTL,	KC_LWIN,	KC_LALT,										KC_SPC, 							KC_RALT,	MO(3),	                KC_LEFT,   	KC_DOWN,	KC_RIGHT),
// layer win Fn
[3] = LAYOUT(
	_______, 	KC_BRID,  	KC_BRIU,  	_______, 	_______,  	_______,  	_______,  	KC_MPRV,  	KC_MPLY,  	KC_MNXT, 	KC_MUTE, 	KC_VOLD, 	KC_VOLU, 	KC_INS,	    _______,
	_______, 	LNK_BLE1,  	LNK_BLE2,  	LNK_BLE3,  	LNK_RF,   	_______,   	_______,   	_______,   	_______,   	_______,  	_______,   	_______,	_______, 	_______,	KC_END,	
	RGB_TOG,	_______,   	_______,   	_______,  	_______,   	_______,   	_______,   	_______,   	_______,   	_______,  	_______,   	DEV_RESET,	SLEEP_MODE, BAT_SHOW,	_______,	
	_______,	_______,   	_______,   	_______,  	_______,   	_______,   	_______,	_______,   	_______,   	_______,  	_______,	_______, 	_______,                _______,
	_______,				_______,   	_______,   	TG(CODEX_LAYER),	_______,   	_______,   	_______,	MO(4), 		RGB_SPD,	RGB_SPI,	_______,	_______,	RGB_VAI,
	_______,	_______,	_______,										_______, 							_______,	MO(3),					RGB_MOD,    RGB_VAD,	RGB_HUI),
// layer side led fn+m
[4] = LAYOUT(
	_______, 	_______,  	_______,  	_______, 	_______,  	_______,  	_______,  	_______,  	_______,  	_______, 	_______, 	_______, 	_______, 	_______,	_______,
	_______, 	_______,   	_______,   	_______,  	_______,   	_______,   	_______,   	_______,   	_______,   	_______,  	_______,   	_______,	_______, 	_______,	_______,
	_______, 	_______,  	_______,  	_______,  	_______,   	_______,   	_______,   	_______,   	_______,   	_______,  	_______,   	_______,	_______, 	_______,	_______,
	_______,	_______,   	_______,   	_______,  	_______,   	_______,   	_______,	_______,   	_______,   	_______,  	_______,	_______, 	_______,                _______,
	_______,				_______,   	_______,   	RGB_TEST,  	_______,   	_______,   	_______,	_______, 	SIDE_SPD,	SIDE_SPI,	_______,	_______,	SIDE_VAI,
	_______,	_______,	_______,										_______, 							_______,	MO(4),   	        	SIDE_MOD,   SIDE_VAD,	SIDE_HUI),
// layer reserved
[5] = LAYOUT(
	_______, 	_______,  	_______,  	_______, 	_______,  	_______,  	_______,  	_______,  	_______,  	_______, 	_______, 	_______, 	_______, 	_______,	_______,
	_______, 	_______,   	_______,   	_______,  	_______,   	_______,   	_______,   	_______,   	_______,   	_______,  	_______,   	_______,	_______, 	_______,	_______,	
	_______, 	_______,  	_______,  	_______,  	_______,   	_______,   	_______,   	_______,   	_______,   	_______,  	_______,   	_______,	_______, 	_______,	_______,	
	_______,	_______,   	_______,   	_______,  	_______,   	_______,   	_______,	_______,   	_______,   	_______,  	_______,	_______, 	_______,                _______,
	_______,				_______,   	_______,   	_______,  	_______,   	_______,   	_______,	_______, 	_______,	_______,	_______,	_______,	_______,
	_______,	_______,	_______,										_______, 							_______,	_______,			    _______,    _______,    _______),
// layer reserved
[REASONING_LAYER] = LAYOUT(
	_______, 	_______,  	_______,  	_______, 	_______,  	_______,  	_______,  	_______,  	_______,  	_______, 	_______, 	_______, 	_______, 	_______,	_______,
	_______, 	_______,   	_______,   	_______,  	_______,   	_______,   	_______,   	_______,   	_______,   	_______,  	_______,   	_______,	_______, 	_______,	_______,	
	_______, 	_______,  	_______,  	_______,  	_______,   	_______,   	_______,   	_______,   	_______,   	_______,  	_______,   	_______,	_______, 	_______,	_______,	
	_______,	_______,   	_______,   	_______,  	_______,   	_______,   	_______,	_______,   	_______,   	_______,  	_______,	_______, 	_______,                _______,
	_______,				_______,   	_______,   	_______,  	_______,   	_______,   	_______,	_______, 	_______,	_______,	_______,	_______,	_______,
	_______,	_______,	_______,										_______, 							_______,	_______,			    _______,    _______,    _______),
[CODEX_LAYER] = LAYOUT(
    TG(CODEX_LAYER), KC_F1, KC_F2, KC_F3, KC_F4, LGUI(LSFT(KC_A)), LGUI(KC_N), LGUI(LALT(KC_P)), LGUI(KC_P), LCTL(LSFT(KC_G)), LCTL(LALT(LGUI(KC_P))), LGUI(LSFT(KC_B)), LGUI(LALT(KC_A)), _______,    TG(REASONING_LAYER),
    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    
    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    
    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,                _______,
    _______,                _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,    _______,
    _______,    _______,    _______,                                        _______,                            _______,    _______,                _______,    _______,    _______),
};

#if defined(ENCODER_MAP_ENABLE)
const uint16_t PROGMEM encoder_map[][NUM_ENCODERS][NUM_DIRECTIONS] = {
    [0] = {ENCODER_CCW_CW(KC_VOLD, KC_VOLU) },
    [1] = {ENCODER_CCW_CW(KC_VOLD, KC_VOLU) },
    [2] = {ENCODER_CCW_CW(KC_VOLD, KC_VOLU) },
    [3] = {ENCODER_CCW_CW(KC_VOLD, KC_VOLU) },
    [4] = {ENCODER_CCW_CW(KC_VOLD, KC_VOLU) },
    [5] = {ENCODER_CCW_CW(KC_VOLD, KC_VOLU) },
    // Private Codex-sidebar controller triggers. The local macOS helper owns
    // these only when Codex is frontmost, so the physical knob always targets
    // the conversation sidebar rather than whichever panel holds the pointer.
    [CODEX_LAYER] = {ENCODER_CCW_CW(LCTL(LALT(LGUI(KC_F19))), LCTL(LALT(LGUI(KC_F20)))) },
    [REASONING_LAYER] = {ENCODER_CCW_CW(LGUI(LALT(LSFT(KC_COMM))), LGUI(LALT(LSFT(KC_DOT)))) }
};
#endif


const is31_led PROGMEM g_is31_leds[RGB_MATRIX_LED_COUNT] = {
    {0, A_12,   B_12,   C_12},   
    {0, A_11,   B_11,   C_11},   
    {0, A_10,   B_10,   C_10},   
    {0, A_9,    B_9,    C_9},    
    {0, D_12,   E_12,   F_12},   
    {0, D_11,   E_11,   F_11},   
    {0, D_10,   E_10,   F_10},   
    {0, D_9,    E_9,    F_9},    
    {1, D_13,   E_13,   F_13},   
    {1, D_12,   E_12,   F_12},   
    {1, D_11,   E_11,   F_11},   
    {1, D_10,   E_10,   F_10},   
    {1, G_13,   H_13,   I_13},   
    {1, J_7,    K_7,    L_7},    
    {0, A_1,    B_1,    C_1},    
    {0, A_2,    B_2,    C_2},    
    {0, A_3,    B_3,    C_3},    
    {0, A_4,    B_4,    C_4},    
    {0, A_5,    B_5,    C_5},    
    {0, A_6,    B_6,    C_6},    
    {0, A_7,    B_7,    C_7},    
    {0, A_8,    B_8,    C_8},    
    {1, D_1,    E_1,    F_1},    
    {1, D_2,    E_2,    F_2},    
    {1, D_3,    E_3,    F_3},    
    {1, D_4,    E_4,    F_4},    
    {1, D_5,    E_5,    F_5},    
    {1, D_6,    E_6,    F_6},    
    {1, J_8,    K_8,    L_8},    
    {0, D_1,    E_1,    F_1},    
    {0, D_2,    E_2,    F_2},    
    {0, D_3,    E_3,    F_3},    
    {0, D_4,    E_4,    F_4},    
    {0, D_5,    E_5,    F_5},    
    {0, D_6,    E_6,    F_6},    
    {0, D_7,    E_7,    F_7},    
    {0, D_8,    E_8,    F_8},    
    {1, G_1,    H_1,    I_1},    
    {1, G_2,    H_2,    I_2},    
    {1, G_3,    H_3,    I_3},    
    {1, G_5,    H_5,    I_5},    
    {1, G_4,    H_4,    I_4},    
    {1, G_6,    H_6,    I_6},    
    {1, G_9,    H_9,    I_9},    
    {0, G_1,    H_1,    I_1},    
    {0, G_2,    H_2,    I_2},    
    {0, G_3,    H_3,    I_3},    
    {0, G_4,    H_4,    I_4},    
    {0, G_5,    H_5,    I_5},    
    {0, G_6,    H_6,    I_6},    
    {0, G_7,    H_7,    I_7},    
    {0, G_8,    H_8,    I_8},    
    {1, J_1,    K_1,    L_1},    
    {1, J_2,    K_2,    L_2},    
    {1, J_3,    K_3,    L_3},    
    {1, J_4,    K_4,    L_4},    
    {1, J_5,    K_5,    L_5},    
    {1, A_12,   B_12,   C_12},   
    {0, J_1,    K_1,    L_1},    
    {0, J_2,    K_2,    L_2},    
    {0, J_3,    K_3,    L_3},    
    {0, J_4,    K_4,    L_4},    
    {0, J_5,    K_5,    L_5},    
    {0, J_6,    K_6,    L_6},    
    {0, J_7,    K_7,    L_7},    
    {0, J_8,    K_8,    L_8},    
    {0, J_9,    K_9,    L_9},    
    {1, G_11,   H_11,   I_11},   
    {1, G_10,   H_10,   I_10},   
    {1, J_10,   K_10,   L_10},   
    {1, J_6,    K_6,    L_6},    
    {0, G_12,   H_12,   I_12},   
    {0, G_11,   H_11,   I_11},   
    {0, G_10,   H_10,   I_10},   
    {0, G_9,    H_9,    I_9},    
    {0, J_12,   K_12,   L_12},   
    {0, J_11,   K_11,   L_11},   
    {1, J_11,   K_11,   L_11},   
    {1, J_12,   K_12,   L_12},   
    {1, J_13,   K_13,   L_13},   
    
    {1, A_5,    B_5,    C_5},      
    {1, A_4,    B_4,    C_4},       
    {1, A_3,    B_3,    C_3},       
    {1, A_2,    B_2,    C_2},       
    {1, A_1,    B_1,    C_1},         
};
