class HiddenMethod:
    def __init__(self, func, hide_when_api=True, message=None):
        self.func = func
        self.hide_when_api = hide_when_api
        self.message = message or f"该方法 '{func.__name__}' 在API模式下不可用"
    
    def __get__(self, instance, owner):
        if instance is None:
            return self
        
        if self.hide_when_api and instance.is_for_api:
            # 返回一个替代函数，而不是真正的方法
            print(f"⚠️ 提示：{self.message}")
            return None  # 或者返回其他默认值
        
        return self.func.__get__(instance, owner)