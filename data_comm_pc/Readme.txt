data_comm_pc/
├── main.py                 # 程序主入口，应用启动文件
├── business/               # 业务逻辑层
│   └── ground_station.py   # 地面站核心业务逻辑与状态管理
├── config/                 # 全局配置层
│   └── ground_station_config.py  # 地面站运行参数统一配置管理
├── core/                   # 核心调度层
│   └── app_assembler.py    # 应用组装器，负责模块生命周期与依赖管理
├── protocol/               # 协议编解码层
│   ├── message_types.py    # 消息类型枚举与通信常量定义
│   ├── data_message.py     # 业务数据报文的编码封装与解码解析
│   └── heartbeat_message.py # 心跳报文的编解码与保活逻辑支撑
├── transport/              # 网络传输层
│   ├── base_receiver.py    # 数据接收器抽象基类，定义统一接口
│   ├── factory.py          # 接收器工厂，动态创建不同协议的传输实例
│   ├── tcp_receiver.py     # TCP 协议数据接收器实现
│   └── udp_receiver.py     # UDP 协议数据接收器实现
├── ui/                     # 界面交互层
│   └── main_window.py      # 主窗口界面与用户交互逻辑
└── utils/                  # 通用工具层
    └── attitude.py         # 姿态数据解析与单位换算工具