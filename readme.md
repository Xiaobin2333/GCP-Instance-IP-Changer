# 一个简单的gcp实例ip更改器

## 注意

此脚本需要中国大陆的服务器才有效，它可以帮助您的服务器不被GFW阻止。

如果是在中国大陆时你需要配置可以正常访问Google的代理地址(除非你能正常访问Google)。

如果是在非中国大陆时你需要配置运行于中国大陆服务器的检测接口地址。

- [服务器端口通断检测接口](https://github.com/Xiaobin2333/Check-Port-API)

## 使用教程

1. 使用git克隆此仓库

    `git clone https://github.com/Xiaobin2333/GCP-Instance-IP-Changer.git`

2. 进入到目录中

    `cd GCP-Instance-IP-Changer`

3. 安装环境

    `pip install -r requirements.txt`

4. 在 `config.json` 中编写配置文件

```json
{
    "project_name": "atomic-envelope-123456",   // 项目名称
    "instance_name": "instance-1",              // 实例名称
    "ip_name": "ip-test",                       // IP 地址名称
    "zone_name": "asia-east1-a",                // 区域名称
    "port": 443,                                // 端口号
    "round_time": 600,                          // 检测间隔时间
    // 如果是在 GCP 实例上运行，则无需设置此项
    "key_path": "key.json",                     // 密钥文件
    // 如果是在非中国大陆运行，则需要配置检测接口地址
    "tcping_server": "",                        // 检测接口地址
    // 如果是在中国大陆运行，则需要配置代理
    "proxy": ""                                 // 代理地址
}
```

5. 运行脚本

    `python3 gcp.py`