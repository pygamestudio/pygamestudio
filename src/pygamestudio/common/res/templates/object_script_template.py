import pygamestudio as studio


class ObjectScript:
    def __init__(self, obj):
        self.obj = obj
    
    def on_start(self):
        """
        对象进入场景回调函数。
        当对象在运行时被创建并进入场景时执行一次，在主循环开始前触发。

        Object lifecycle callback.
        Executes exactly once when the object is created and enters the scene at runtime,
        before the main loop starts.
        """
        pass

    def on_update(self, dt:float):
        """
        每帧更新回调函数，每一帧循环都会执行。
        :param dt: 距离上一帧的时间（单位：秒）

        Per-frame update callback, runs every single frame in the main loop.
        :param dt: Time elapsed since last frame (in seconds)
        """
        pass
    
    def on_destroy(self):
        """
        对象销毁回调函数。
        当对象从场景中移除、即将被销毁时执行一次，用于清理资源或停止相关逻辑。

        Object destruction callback.
        Executes exactly once when the object is removed from the scene and about to be destroyed;
        use it to release resources or stop related logic.
        """
        pass