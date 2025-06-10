import requests
import warnings
import os
from appLog import Logger
from datetime import datetime
from PyQt5.QtCore import QObject, pyqtSignal



class SignalBus(QObject):
    """全局信号总线，用于跨类发送消息"""
    error_occurred = pyqtSignal(str)  # 错误消息信号
    info_occurred = pyqtSignal(str)   # 普通消息信号

# 创建全局信号实例
signal_bus = SignalBus()

warnings.filterwarnings("ignore", category=DeprecationWarning)
# 创建全局日志实例
log = Logger('app.log', level='debug')



class HttpsRequest:
    def __init__(self):
        pass

    def send_request(self, url):
        try:
            # 发送 GET 请求，verify=False 表示不验证 SSL 证书
            response = requests.get(url, verify=False)
            # 检查响应状态码
            if response.status_code == 200:
                return response.json()
            else:
                error_msg = f"GET请求失败，状态码: {response.status_code}，错误内容: {response.text}"
                log.logger.error(error_msg)
                signal_bus.error_occurred.emit(error_msg)  # 发送错误信号
                return response.json()

        except requests.exceptions.RequestException as e:
            error_msg = f"GET请求发生错误: {e}"
            log.logger.error(error_msg)
            signal_bus.error_occurred.emit(error_msg)  # 发送错误信号
            return e

    def download_file(self, url):
        try:
            # 设置 verify=False 来忽略证书验证（不建议在生产环境中直接使用）
            response = requests.get(url, stream=True, verify=False)
            response.raise_for_status()

            url_filename = url.split('/')[-1]
            # 生成时间戳（格式：YYYYMMDD_HHMMSS）
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            desktop_path = os.path.join(os.path.expanduser('~'), 'Desktop')
            local_filename = f"{os.path.splitext(url_filename)[0]}_错误模板{timestamp}{os.path.splitext(url_filename)[1]}"

            # 拼接桌面路径和文件名
            full_path = os.path.join(desktop_path, local_filename)
            with open(full_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            success_msg = f"导入文件数据异常！！错误模板已下载至桌面,路径为:{full_path}"
            log.logger.info(success_msg)
            signal_bus.info_occurred.emit(success_msg)
            return full_path

        except requests.RequestException as e:
            error_msg = f"下载文件失败: {e}"
            log.logger.error(error_msg)
            signal_bus.error_occurred.emit(error_msg)  # 发送错误信号
            return e

class HttpsPostRequest:
    def __init__(self):
        pass

    def send_request(self, url, data=None, json=None, headers=None,  files=None):
        try:
            # 发送 POST 请求，verify=False 表示不验证 SSL 证书
            response = requests.post(url, data=data, json=json, headers=headers, files=files, verify=False)
            # 检查响应状态码
            if response.status_code == 200:
                try:
                    return response
                except ValueError:
                    return response.text
            else:
                error_msg = f"POST请求失败，状态码: {response.status_code}，错误内容: {response.text}"
                log.logger.error(error_msg)
                signal_bus.error_occurred.emit(error_msg)  # 发送错误信号
                return response

        except requests.exceptions.RequestException as e:
            error_msg = f"POST请求发生错误: {e}"
            log.logger.error(error_msg)
            signal_bus.error_occurred.emit(error_msg)  # 发送错误信号
            return e

