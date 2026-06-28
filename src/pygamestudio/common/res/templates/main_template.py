import pygamestudio as studio


class Game(studio.Game):
    def __init__(self):
        super().__init__()

    def on_start(self):
        """
        游戏启动生命周期回调。
        在游戏初始化完成、主循环开始前仅执行一次。

        Game startup lifecycle callback.
        Executes exactly once after the game initialization and before the main loop starts.
        """
        pass

    def on_update(self, dt:float):
        """
        每帧更新回调，每一帧循环都会执行。
        :param dt: 距离上一帧的时间（单位：秒）

        Per-frame update callback, runs every single frame in the main loop.
        :param dt: Time elapsed since last frame (in seconds)
        """
        screen = studio.get_screen()
        studio.load_scene(screen)
        
        # 可通过路径或uuid获取对象。
        # Get an object by its path or uuid.
        # obj = studio.get_object_by_path('')
        # obj = studio.get_object_by_uuid('')

    def on_quit(self):
        """
        游戏退出回调。
        主循环结束后，资源被销毁前执行一次。

        Game exit lifecycle callback.
        Executes once after the main loop exits and before all resources are released.
        """
        pass


if __name__ == '__main__':
    game = Game()
    game.run()