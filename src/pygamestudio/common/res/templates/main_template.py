import os
import sys
import pygame
from pathlib import Path
from pygamestudio.api.runtime.scene import load_scene
from pygamestudio.api.runtime.config import get_project_config

# setup pygamestudio project env to get the project config 
project_path = Path(__file__).parent.resolve().as_posix()
os.environ['PROJECT_PATH'] = project_path
project_config = get_project_config()

# pygame setup
pygame.init()
pygame.display.set_caption(project_config['caption'])
screen = pygame.display.set_mode(project_config['screen_size'])
clock = pygame.time.Clock()

running = True
while running:
    # poll for events
    # pygame.QUIT event means the user clicked X to close your window
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    # load the scene created in pygamestudio
    # if no scene_path is provided, the default current_scene from the project config will be loaded
    load_scene(screen)

    # flip() the display to put your work on screen and limits FPS to 60
    pygame.display.flip()
    clock.tick(60)

pygame.quit()
sys.exit()
