import pygame
import math

class TransformableShape:
    def __init__(self, shape_type, color, pos, size_params):
        """
        shape_type: "rect", "circle", "polygon", "ellipse"
        color: RGB颜色
        pos: (x, y) 中心位置
        size_params: 根据类型不同传入不同参数
        """
        self.shape_type = shape_type
        self.color = color
        self.pos = pos
        self.size_params = size_params
        self.angle = 0
        self.scale = 1.0
        
        # 创建原始 Surface
        self.create_original_surface()
    
    def create_original_surface(self):
        """根据图形类型创建对应的 Surface"""
        if self.shape_type == "rect":
            width, height = self.size_params
            self.original_surface = pygame.Surface((width, height), pygame.SRCALPHA)
            self.original_surface.fill(self.color)
            
        elif self.shape_type == "circle":
            radius = self.size_params
            diameter = radius * 2
            self.original_surface = pygame.Surface((diameter, diameter), pygame.SRCALPHA)
            pygame.draw.circle(self.original_surface, self.color, (radius, radius), radius)
            
        elif self.shape_type == "ellipse":
            width, height = self.size_params
            self.original_surface = pygame.Surface((width, height), pygame.SRCALPHA)
            pygame.draw.ellipse(self.original_surface, self.color, 
                               (0, 0, width, height))
            
        elif self.shape_type == "polygon":
            points = self.size_params  # 点列表
            # 计算 Surface 大小
            min_x = min(p[0] for p in points)
            max_x = max(p[0] for p in points)
            min_y = min(p[1] for p in points)
            max_y = max(p[1] for p in points)
            width = max_x - min_x + 1
            height = max_y - min_y + 1
            
            self.original_surface = pygame.Surface((width, height), pygame.SRCALPHA)
            # 平移点到 Surface 内
            adjusted_points = [(p[0] - min_x, p[1] - min_y) for p in points]
            pygame.draw.polygon(self.original_surface, self.color, adjusted_points)
    
    def get_transformed_surface(self):
        """获取变换后的 Surface"""
        # 缩放
        scaled_size = (int(self.original_surface.get_width() * self.scale),
                      int(self.original_surface.get_height() * self.scale))
        scaled_surface = pygame.transform.scale(self.original_surface, scaled_size)
        
        # 旋转
        rotated_surface = pygame.transform.rotate(scaled_surface, self.angle)
        
        return rotated_surface
    
    def draw(self, screen):
        """绘制图形"""
        transformed = self.get_transformed_surface()
        rect = transformed.get_rect(center=self.pos)
        screen.blit(transformed, rect)
        
        # 可选：绘制边框表示原始位置
        # pygame.draw.circle(screen, (0, 0, 0), self.pos, 3)

# 使用示例
pygame.init()
screen = pygame.display.set_mode((800, 600))
clock = pygame.time.Clock()

# 创建不同类型的图形
shapes = [
    TransformableShape("rect", (255, 0, 0), (200, 200), (150, 100)),
    TransformableShape("circle", (0, 255, 0), (400, 200), 50),
    TransformableShape("ellipse", (0, 0, 255), (600, 200), (120, 80)),
    TransformableShape("polygon", (255, 255, 0), (300, 400), 
                      [(50, 10), (10, 80), (30, 90), (70, 90), (90, 80)]),
]

running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
    
    screen.fill((255, 255, 255))
    
    # 更新并绘制所有图形
    for i, shape in enumerate(shapes):
        # 不同的动画效果
        shape.angle += 1
        shape.scale = 1.0 + math.sin(pygame.time.get_ticks() * 0.002 + i) * 0.3
        shape.draw(screen)
    
    pygame.display.flip()
    clock.tick(60)

pygame.quit()