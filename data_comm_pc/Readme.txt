
data_comm_pc/
├── main.py                 # 程序入口，启动UI与通信服务
├── business/               # 业务逻辑层
│   ├── __init__.py
│   └── ground_station.py   # 地面站核心业务调度
├── config/                 # 配置层
│   ├── __init__.py
│   └── ground_station_config.py  # 全局参数、网络、UI配置
├── protocol/               # 通信协议解析模块（预留扩展）
├── transport/              # 底层传输通信层
│   ├── __init__.py
│   ├── base_receiver.py    # 接收器抽象基类，统一接口
│   ├── tcp_receiver.py     # TCP数据接收实现
│   └── udp_receiver.py     # UDP数据接收实现
├── ui/                     # 图形界面层
│   ├── __init__.py
│   └── main_window.py      # 主窗口UI逻辑
└── utils/                  # 通用工具函数
    ├── __init__.py
    └── attitude.py         # 姿态解算、坐标转换等工具