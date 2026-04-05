import pygame
import sys

pygame.init()
screen = pygame.display.set_mode((800, 600))
font = pygame.font.SysFont('Arial', 72)

# 创建一个较小的 Surface（200x50）
small_surface = pygame.Surface((200, 50))
small_surface.fill((200, 200, 200))

# 创建较大的文本（需要300x80的空间）
text = font.render("ABCDEFGHIJK", True, (255, 0, 0))
print(f"文本实际尺寸: {text.get_size()}")  # 可能输出 (280, 70)

# 将大文本绘制到小Surface上
small_surface.blit(text, (0, 0))  # 超出部分会被裁剪！

# 主循环
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    
    screen.fill((255, 255, 255))
    screen.blit(small_surface, (100, 100))
    
    # 同时显示完整文本作为对比
    screen.blit(text, (100, 200))
    
    pygame.display.flip()

pygame.quit()
sys.exit()