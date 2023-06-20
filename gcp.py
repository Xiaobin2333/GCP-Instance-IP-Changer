import time
import os
import sys
import time
import json
import logging
import requests
from tcping import Ping
from google.cloud import compute_v1
from google.auth import compute_engine
from google.oauth2 import service_account


# 定义日志格式
level = logging.INFO
logging.basicConfig(
    level=level, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# 读取配置文件
try:
    if not os.path.exists("config.json"):
        logger.error("Config file not found")
        with open("config.json", "w") as f:
            f.write("""{
                "project_name": "atomic-envelope-123456",
                "instance_name": "instance-1",
                "ip_name": "ip-test",
                "zone_name": "asia-east1-a",
                "port": 443,
                "round_time": 600,
                "key_path": "key.json",
                "tcping_server": "",
                "proxy": ""
            }""")
        sys.exit(1)
    else:
        with open("config.json", "r") as f:
            config = json.load(f)
            project_name = config["project_name"]
            instance_name = config["instance_name"]
            ip_name = config["ip_name"]
            zone_name = config["zone_name"]
            port = config["port"]
            round_time = config["round_time"]
            key_path = config["key_path"]
            tcping_server = config["tcping_server"]
            proxy_url = config["proxy"]
            if key_path != "":
                credentials = service_account.Credentials.from_service_account_file(
                    key_path)
            else:
                credentials = compute_engine.Credentials()
            if tcping_server != "":
                tcping_srver = tcping_server
            else:
                tcping_server = None
            if proxy_url != "":
                os.environ["http_proxy"] = proxy_url
                os.environ["https_proxy"] = proxy_url
            # 检查json文件是否存在ignore参数
            try:
                ignore = config["ignore"]
                if ignore == "True":
                    ignore_loc = True
                else:
                    ignore_loc = False
            except:
                ignore_loc = False
                    
except:
    logger.error("Error reading config")
    sys.exit(1)


compute_client = compute_v1.InstancesClient(credentials=credentials)
address_client = compute_v1.AddressesClient(credentials=credentials)
region_name = zone_name[:-2]


class GCPAPI:
    def __init__(self, project_name, instance_name, ip_name, zone_name, region_name):
        self.project_name = project_name
        self.instance_name = instance_name
        self.ip_name = ip_name
        self.zone_name = zone_name
        self.region_name = region_name

    # 记录 IP 地址历史
    def record_ip(self, ip):
        if ip not in self.read_ip():
            with open("ip_history", "a") as f:
                f.write(ip + "\n")

    # 读取 IP 地址历史
    def read_ip(self):
        ip_list = []
        if not os.path.exists("ip_history"):
            with open("ip_history", "w") as f:
                return []
        else:
            with open("ip_history", "r") as f:
                for line in f.readlines():
                    ip_list.append(line.strip())
        return ip_list

    # 获取实例 IP 地址
    def get_instance_ip(self):
        logger.info("Getting instance IP address...")
        instance = compute_client.get(
            project=self.project_name, zone=self.zone_name, instance=self.instance_name)
        logger.debug(instance)
        try:
            ip = instance.network_interfaces[0].access_configs[0].nat_i_p
        except Exception as e:
            if str(e) == "list index out of range":
                ip = None
            else:
                raise Exception("Get instance IP failed")
        return ip

    # 删除未使用的 IP 地址
    def delete_unused_ip(self):
        logger.info("Deleting unused IP address...")
        for address in address_client.list(project=self.project_name, region=self.region_name):
            logger.debug(address)
            if address.status == "RESERVED":
                address_client.delete(
                    project=self.project_name, region=self.region_name, address=address.name)
                # 等待 IP 地址删除完成
                while True:
                    try:
                        address_client.get(
                            project=self.project_name, region=self.region_name, address=address.name)
                        logger.debug(address)
                    except:
                        break
                    else:
                        time.sleep(1)

    # 解绑实例 IP 地址
    def unbind_instance_ip(self):
        logger.info("Unbinding instance IP address...")
        instance = compute_client.get(
            project=self.project_name, zone=self.zone_name, instance=self.instance_name)
        logger.debug(instance)
        for network_interface in instance.network_interfaces:
            for access_config in network_interface.access_configs:
                compute_client.delete_access_config(
                    project=self.project_name,
                    zone=self.zone_name,
                    instance=self.instance_name,
                    access_config=access_config.name,
                    network_interface=network_interface.name,
                )
        # 等待 IP 地址解绑完成
        while True:
            instance = compute_client.get(
                project=self.project_name, zone=self.zone_name, instance=self.instance_name)
            logger.debug(instance)
            if len(instance.network_interfaces[0].access_configs) == 0:
                break
            else:
                time.sleep(1)

    # 添加新的静态 IP 地址
    def add_static_ip(self):
        logger.info("Adding static IP address...")
        ip_name = self.ip_name + "-" + str(int(time.time()))
        address = address_client.insert(
            project=self.project_name, region=self.region_name, address_resource={"name": ip_name})
        logger.debug(address)
        # 等待 IP 地址创建完成
        while True:
            address = address_client.get(
                project=self.project_name, region=self.region_name, address=ip_name)
            logger.debug(address)
            if address.status == "RESERVED":
                break
            else:
                time.sleep(1)
        return address.address

    # 将新的静态 IP 地址绑定到实例
    def bind_static_ip(self, ip):
        logger.info("Binding static IP address to instance...")
        compute_client.add_access_config(
            project=self.project_name,
            zone=self.zone_name,
            instance=self.instance_name,
            network_interface="nic0",
            access_config_resource={
                "name": "External NAT", "nat_i_p": ip},
        )
        # 等待 IP 地址绑定完成
        while True:
            instance = compute_client.get(
                project=self.project_name, zone=self.zone_name, instance=self.instance_name)
            logger.debug(instance)
            if len(instance.network_interfaces[0].access_configs) == 1:
                break
            else:
                time.sleep(1)

    # 获取静态 IP 地址数量(防止 IP 地址配额不足)
    def get_static_ip_count(self):
        logger.info("Getting static IP address count...")
        count = 0
        for address in address_client.list(project=self.project_name, region=self.region_name):
            logger.debug(address)
            if address.status == "RESERVED":
                count += 1
        return count

    # 更换实例 IP 地址
    def change_ip(self):
        old_ip = self.get_instance_ip()
        try_count = 0
        while try_count < 20:
            try_count += 1
            if self.get_static_ip_count() >= 8:
                logger.info(
                    "IP address quota exceeded, deleting unused IP address...")
                self.delete_unused_ip()
            new_ip = self.add_static_ip()
            if new_ip != old_ip and new_ip not in self.read_ip():
                self.unbind_instance_ip()
                self.bind_static_ip(new_ip)
                self.record_ip(new_ip)
                break
            else:
                logger.info("IP address already exists, retrying...")
        self.delete_unused_ip()
        # 如果尝试次数超过 20 次，则休眠 1 小时
        if try_count >= 20:
            logger.info(
                "IP address change try count exceeded, sleeping for 1 hour...")
            time.sleep(3600)
            raise Exception("IP address change try count exceeded")
        logger.info(f"OLD IP: {old_ip} -> NEW IP: {new_ip}")
        return new_ip


class HiddenPrints:
    def __enter__(self):
        self._original_stdout = sys.stdout
        sys.stdout = open(os.devnull, 'w')

    def __exit__(self, exc_type, exc_val, exc_tb):
        sys.stdout.close()
        sys.stdout = self._original_stdout


class CheckGFW:
    # 本地tcping
    def local_tcping(server, port):
        ping = Ping(server, port, 1)
        try:
            with HiddenPrints():
                ping.ping(4)
        except Exception as e:
            return False
        rate = Ping._success_rate(ping)
        # 根据丢包率判断是否被墙
        if float(rate) > 0:
            return True
        return False

    # 远程tcping
    def remote_tcping(server, port):
        url = f"{tcping_server}"
        params = {"server": server, "port": port}
        try:
            response = requests.get(url, params=params, timeout=10)
            if response.status_code == 200:
                if response.text == "True":
                    return True
                elif response.text == "False":
                    return False
            else:
                raise Exception("Remote tcping return error")
        except Exception as e:
            raise Exception("Remote tcping request failed")

    # 第三方tcping
    def other_tcping(server, port):
        url = f"https://ping.gd/api/ip-test/{server}:{port}"
        try:
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                result = response.json()[0]['result']['telnet_alive']
                if result == True:
                    return True
                elif result == False:
                    return False
            else:
                raise Exception("Other tcping return error")
        except Exception as e:
            raise Exception("Other tcping request failed")


# 检查脚本运行地区
def check_location():
    url = "https://api.ip.sb/geoip"
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            if data["country_code"] == "CN":
                return True
            else:
                return False
        else:
            raise Exception("Check location return error")
    except Exception as e:
        raise Exception("Check location error")


if __name__ == "__main__":
    try:
        gcp = GCPAPI(project_name, instance_name,
                     ip_name, zone_name, region_name)
        check = CheckGFW.local_tcping
        if check_location() and not ignore_loc:
            if proxy_url == "":
                logger.error("Running in China, you must set proxy_url")
                time.sleep(10)
                exit()
        else:
            if tcping_server:
                check = CheckGFW.remote_tcping
            else:
                check = CheckGFW.other_tcping
    except Exception as e:
        logger.error(str(e))
        time.sleep(10)
        exit()
    while True:
        try:
            ip = gcp.get_instance_ip()
            if not ip:
                logger.warning("IP is empty, adding IP...")
                try:
                    ip = gcp.change_ip()
                except Exception as e:
                    raise Exception("Add IP failed")
            if check(ip, port):
                logger.info("GCP is ok")
            else:
                logger.info("GCP is blocked")
                try:
                    gcp.change_ip()
                except Exception as e:
                    raise Exception("Change IP failed")
            time.sleep(round_time)
        except Exception as e:
            logger.error(str(e))
            time.sleep(round_time)
            continue
