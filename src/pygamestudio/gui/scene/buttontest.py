import pygame
# pygame.init()
# window = pygame.display.set_mode((800, 600))
# pygame.display.set_caption('按钮示例')

class Button(pygame.sprite.Sprite):
    def __init__(self, image_path, x, y):
        super().__init__()
        self.image = pygame.image.load(image_path)
        self.rect = self.image.get_rect()
        self.rect.x = x
        self.rect.y = y
    def update(self):
        if pygame.mouse.get_pressed() and self.rect.collidepoint(pygame.mouse.get_pos()):
            self.status = 'pressed'  # 模拟按下状态切换
        else:
            self.status = 'normal'  # 恢复常态
    def draw(self, surface):
        surface.blit(self.image, self.rect)  # 根据状态选择图像渲染

# # 创建按钮实例并更新屏幕内容（需循环调用）
# button = Button(image_path='button.png', x=150, y=450)
# while True:
#     for event in pygame.event.get():  # 处理事件（如关闭窗口）
#         if event.type == pygame.QUIT:
#             pygame.quit()
#     window.fill((255, 255, 255))  # 清屏填充白色背景
#     button.draw(window)  # 绘制按钮到屏幕指定位置
#     pygame.display.update()  # 更新显示内容到窗口