# AI图片、模型目录与只读工具

AI仍由服务端检查VIP或ai审批授权。Key使用AES-GCM加密，页面只显示掩码。生产AI网关限制为HTTPS官方域名或`AI_CUSTOM_HOSTS`中精确允许的域名；修改服务商或地址时，模型列表请求不能借用另一地址保存的Key。

## 图片与模型能力

AI设置中明确确认当前模型支持图片/工具。服务商提供的模型目录字段可展示图片能力和上下文长度；缺失值标为未知，不根据模型名猜测。目录按用户、服务商地址、Key隔离缓存24小时；失败可使用旧目录/推荐默认模型，并允许手填。后台每周刷新已保存Key对应的目录。

单次最多4张图片，支持JPEG/PNG/WebP、每张上传上限5MB，服务端转JPEG并去除EXIF。仅允许使用本人未删除的ai或mistake附件；不接受任意URL供服务器抓取。开发本地图像转为data URL，生产七牛图像使用短期签名URL交给模型。历史保存附件key，下一轮重新生成有效URL；不会持久保存签名URL。错题详情可将题干、思路和题目/解析图片带入对话，用户点击发送后才提交给模型。

## 工具和搜索

可显式启用：北京时间、本人已同步学习统计，以及配置了Brave Search Key后的公开网页搜索。统计不会读取其他人的数据，也不包含尚未同步的本机记录。普通问答使用服务商SSE；工具模式等待工具循环结束后显示完整结果与来源，不假装逐Token流式。

每次用户请求最多3次模型请求、6次工具执行、总处理时间120秒。工具名和参数由服务端白名单检查，不提供修改任务、删除记录、代码执行、文件读写或任意URL访问工具。搜索摘要属于不可信数据，结果URL需为HTTP(S)，界面独立显示来源链接；搜索Key不进入客户端或对话历史。

一次用户请求消耗一个日预算单位，失败尝试同样计入；内部工具循环受上述次数限制。北京时间零点重置。Token仅统计服务商实际报告的数值，工具模式累加各轮用量；未报告部分不冒充完整账单。相同对话的并发生成被租约拦截，异常/取消后释放，进程意外中断最多等待5分钟后可重新请求。

## 真实服务配置

```ini
AI_VISION_ENABLED=true
AI_TOOLS_ENABLED=true
AI_SERVER_VISION=false
AI_SERVER_TOOLS=false
BRAVE_SEARCH_API_KEY=
```

前两项是站点开关，后两项仅声明服务器兜底模型的能力，不会赋予模型本身不存在的能力。BYOK模型能力在AI设置里保存。没有搜索配置时明确提示未配置，不进行虚假联网。搜索及模型供应商可能有自己的额度，需要用实际账号联调；仓库测试全部使用mock。

协议参考：[Chat Completions](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)、[Function calling](https://developers.openai.com/api/docs/guides/function-calling)、[Brave Search Web API](https://api-dashboard.search.brave.com/app/documentation/web-search)。这里实现OpenAI兼容协议，不保证每个服务商的每个模型支持全部可选能力。
