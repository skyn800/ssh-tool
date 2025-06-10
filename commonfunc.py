class CommonFunc:
    def __init__(self):
        self.allowed_users = ['patrol', 'robot', 'root']

    def validate_ip(self, ip):
        """
         简单的 IP 地址验证
         @param ip:
         @return:
         """
        parts = ip.split('.')
        return len(parts) == 4 and all(part.isdigit() and 0 <= int(part) <= 255 for part in parts)

    def validate_port(self, port):
        """
       简单的端口验证
       @param port:
       @return:
       """
        try:
            port_int = int(port)
            return 0 <= port_int <= 65535
        except ValueError:
            return False

    def validate_sshuser(self, sshuser):
        """
        简单的用户筛选
        @param sshuser: 输入的用户名
        @return:
        """
        if sshuser in self.allowed_users:
            return True
        else:
            return False

    def check_sysversion(self, version_str):
        major, minor = map(int, version_str.split('.')[:2])  # map(int, ...)--对可迭代对象（如列表）的每个元素应用指定函数（如 int）
        return (major > 3) or (major == 3 and minor >= 17)  # 判断主版本>3或者主版本为3并次版本>=17即可

