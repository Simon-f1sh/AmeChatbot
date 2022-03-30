# bot01
本bot目前仅用于学习和测试用途

maimai相关和群聊互动功能基于千雪bot: https://github.com/Diving-Fish/Chiyuki-Bot

天气图片生成功能修改自和风天气插件: https://github.com/kexue-z/nonebot-plugin-heweather

# bot启动

step0.安装python

step1.项目根目录下执行

```
pip install -r requirement.txt
```

安装依赖

PS: 安装依赖过程中报错可以尝试删除对应的依赖包 应该也不会出什么问题（大概吧

step2.项目根目录下执行

```
python bot.py
```

step3.安装CQHTTP ( https://docs.go-cqhttp.org/ )并启动

生成配置文件时 通信方式选择3：反向websocket通信

生成配置文件后，修改设置universal为ws://[.env.prod中设置的HOST(默认为127.0.0.1)]:[.env.prod中设置的port(默认为5800)]/cqhttp/ws

Example:ws://127.0.0.1:5800/cqhttp/ws

# 大概没什么用的Q&A

Q: 缺少secretId secretkey / heweather_apikey / DEVELOPER_TOKEN

A：联系lez221获取