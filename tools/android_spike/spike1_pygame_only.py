"""
Minimal spike app: proves the p4a toolchain produced a *usable* pygame.

It deliberately exercises the four things the recipe compiles separately, so a
failure names the missing pieces instead of showing a blank screen:

* display / touch input        -> SDL2 + bootstrap
* image.load() (PNG)           -> SDL2_image  (+ png/libjpeg recipes)
* font rendering               -> SDL2_ttf    (needs freetype)
* mixer playback               -> SDL2_mixer

Everything is written to stdout, which `adb logcat -s python` shows. The screen
shows one line per check, so a photo of the device is enough as evidence.
"""

import struct
import sys

import pygame


CHECKS = []


def check(name, func):
    try:
        func()
    except Exception as exc:                     # noqa: BLE001 - spike wants the raw error
        CHECKS.append((name, False, f'{type(exc).__name__}: {exc}'))
        print(f'[SPIKE] {name}: FAIL - {type(exc).__name__}: {exc}', flush=True)
    else:
        CHECKS.append((name, True, 'ok'))
        print(f'[SPIKE] {name}: ok', flush=True)


def beep_bytes():
    """800 Hz square wave, 0.15 s, 16-bit mono 22050 Hz - no numpy needed."""
    rate, seconds = 22050, 0.15
    frames = b''.join(struct.pack('<h', 8000 if (i // 27) % 2 else -8000)
                      for i in range(int(rate * seconds)))
    return frames, rate


def main():
    pygame.init()
    print(f'[SPIKE] python {sys.version.split()[0]}', flush=True)
    print(f'[SPIKE] pygame {pygame.version.ver} (SDL {pygame.get_sdl_version()})', flush=True)

    screen = pygame.display.set_mode((640, 360))
    pygame.display.set_caption('PyGS spike')

    # 1. surface + image round-trip through SDL2_image
    def image_check():
        surface = pygame.Surface((32, 32))
        surface.fill((0, 200, 120))
        pygame.image.save(surface, 'spike.png')
        loaded = pygame.image.load('spike.png')
        assert loaded.get_size() == (32, 32), loaded.get_size()

    # 2. font rendering through SDL2_ttf
    def font_check():
        font = pygame.font.Font(None, 24)
        surface = font.render('font ok 字体', True, (255, 255, 255))
        assert surface.get_width() > 0

    # 3. mixer through SDL2_mixer
    def mixer_check():
        pygame.mixer.init(frequency=22050, size=-16, channels=1)
        frames, _rate = beep_bytes()
        sound = pygame.mixer.Sound(buffer=frames)
        sound.play()

    check('image', image_check)
    check('font', font_check)
    check('mixer', mixer_check)

    font = pygame.font.Font(None, 22)
    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type in (pygame.MOUSEBUTTONDOWN, pygame.FINGERDOWN):
                print(f'[SPIKE] touch/tap {event}', flush=True)
            elif event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                running = False

        screen.fill((20, 20, 24))
        for index, (name, ok, detail) in enumerate(CHECKS):
            color = (120, 220, 160) if ok else (230, 110, 110)
            screen.blit(font.render(f'{name}: {detail}', True, color), (16, 16 + index * 26))
        screen.blit(font.render('tap the screen to log an event', True, (150, 150, 160)), (16, 250))
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == '__main__':
    main()
