import os
import sys
sys.path.insert(0, 'D:\\Github\\pygamestudio\\src')

import pygame
from pathlib import Path
from pygamestudio.api.runtime.config import get_project_config
from pygamestudio.api.runtime.scene import load_scene

PROJECT_PATH = Path(__file__).parent.resolve().as_posix()
os.environ['PROJECT_PATH'] = PROJECT_PATH


pygame.init()
PROJECT_CONFIG = get_project_config()
pygame.display.set_caption(PROJECT_CONFIG['caption'])
screen = pygame.display.set_mode(PROJECT_CONFIG['screen_size'])
clock = pygame.time.Clock()


running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    load_scene(screen)

    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
