"""Runtime physics API: gravity, pause/time scale and queries.

An object is a rigid body when its ``physics_enabled`` is True (see
``game/core/physics.py``): the body uses the object's collision shape, and the
per-object actions (``apply_force``, ``apply_impulse``, ``set_velocity``,
``is_grounded``, ...) live on the object itself.
"""
from pygamestudio.api.core.scene import scene_loader


def get_physics_world():
    """当前场景的物理世界（编辑器或未加载场景时为 None）。The physics world of the running scene, or None."""
    return scene_loader.physics_world()


def set_gravity(gravity):
    """
    设置全局重力。
    :param gravity: (x, y) 像素/秒²，y 向下为正；默认 (0, 980)

    The gravity every body falls with: ``(0, 980)`` is the default, ``(0, 0)``
    makes space and a negative y pulls upwards.
    """
    world = scene_loader.physics_world()
    if world is not None:
        world.set_gravity(gravity)


def get_gravity() -> tuple:
    """当前重力 (x, y)，单位像素/秒²。The current gravity in pixels per second squared."""
    world = scene_loader.physics_world()
    return tuple(world.gravity) if world is not None else (0.0, 980.0)


def set_physics_enabled(enabled: bool):
    """
    暂停或恢复整个物理模拟（对象停在原地）。
    :param enabled: True = 运行，False = 暂停

    Pause or resume the simulation. Bodies keep their positions while it is
    off - handy for a menu that freezes the world behind it.
    """
    world = scene_loader.physics_world()
    if world is not None:
        world.enabled = bool(enabled)


def is_physics_enabled() -> bool:
    """物理模拟当前是否在运行。True while the simulation steps."""
    world = scene_loader.physics_world()
    return bool(world.enabled) if world is not None else False


def set_physics_time_scale(scale: float):
    """
    物理时间倍率：0.5 = 慢动作，2 = 快进，0 = 暂停。
    :param scale: 时间倍率（>= 0）

    Slow motion / fast forward for the physics only - the rest of the game
    keeps running at normal speed.
    """
    world = scene_loader.physics_world()
    if world is not None:
        world.time_scale = max(0.0, float(scale))


def get_physics_time_scale() -> float:
    """当前物理时间倍率。The current physics time scale."""
    world = scene_loader.physics_world()
    return float(world.time_scale) if world is not None else 1.0


def physics_raycast(start, end):
    """
    从 start 到 end 发一条射线，返回第一个被击中的物理对象（没有则 None）。
    :param start: 起点（世界坐标，像素）
    :param end: 终点（世界坐标，像素）

    The first physics object a ray from ``start`` to ``end`` hits, or None.
    Handy for line-of-sight checks and "is there ground below me" probes.
    """
    world = scene_loader.physics_world()
    return world.raycast(start, end) if world is not None else None
