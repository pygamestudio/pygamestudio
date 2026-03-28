import pygame
import multiprocessing
import sys
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QDialog

def run_pygame_process(queue=None):
    """在独立进程中运行 Pygame"""
    try:
        pygame.init()
        
        # 设置环境变量避免冲突
        import os
        os.environ['SDL_VIDEO_WINDOW_POS'] = '100,100'
        
        screen = pygame.display.set_mode((400, 300))
        pygame.display.set_caption("Pygame 子进程")
        
        running = True
        clock = pygame.time.Clock()
        
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if queue:
                        queue.put(f"按键: {pygame.key.name(event.key)}")
            
            screen.fill((0, 0, 0))
            # 绘制一些内容
            pygame.draw.circle(screen, (255, 0, 0), (200, 150), 50)
            pygame.display.flip()
            clock.tick(60)
        
        pygame.quit()
        
    except Exception as e:
        print(f"Pygame 进程错误: {e}")
        if queue:
            queue.put(f"错误: {e}")

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.pygame_process = None
        self.message_queue = None
        
        # 创建按钮
        start_btn = QPushButton("启动 Pygame 进程", self)
        start_btn.clicked.connect(self.start_pygame)
        start_btn.move(0, 0)
        
        stop_btn = QPushButton("停止 Pygame 进程", self)
        stop_btn.clicked.connect(self.stop_pygame)
        stop_btn.move(0, 50)
        
        dialog_btn = QPushButton("打开模态框", self)
        dialog_btn.clicked.connect(self.open_dialog)
        dialog_btn.move(0, 100)
        
        self.resize(200, 200)
    
    def start_pygame(self):
        """启动 Pygame 子进程"""
        if self.pygame_process is None or not self.pygame_process.is_alive():
            # 使用队列进行进程间通信
            self.message_queue = multiprocessing.Queue()
            
            self.pygame_process = multiprocessing.Process(
                target=run_pygame_process,
                args=(self.message_queue,)
            )
            self.pygame_process.start()
            print("Pygame 进程已启动")
    
    def stop_pygame(self):
        """停止 Pygame 子进程"""
        if self.pygame_process and self.pygame_process.is_alive():
            self.pygame_process.terminate()
            self.pygame_process.join()
            print("Pygame 进程已停止")
    
    def open_dialog(self):
        """打开模态框（不会影响 Pygame 进程）"""
        dialog = QDialog(self)
        dialog.setWindowTitle("模态框")
        dialog.setModal(True)
        dialog.resize(300, 200)
        dialog.exec()
    
    def closeEvent(self, event):
        """关闭主窗口时清理"""
        self.stop_pygame()
        event.accept()

if __name__ == "__main__":
    # 设置多进程启动方式（对于 Windows 是必需的）
    multiprocessing.set_start_method('spawn', force=True)
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())