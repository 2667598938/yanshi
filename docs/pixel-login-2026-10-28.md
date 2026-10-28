# Q版像素登录页

日期：2026-10-28。按用户最新反馈重做登录界面，采用像素学习小屋主题。本次只改账号页面的呈现与插画降级，不修改后端、准入规则、其他业务页或开场。

## 页面

- 奶油纸色、鼠尾草绿、杏桃点缀；像素窗口标题栏、书本图形、细网格背景和有按压反馈的按钮。中文使用清晰系统字体，像素风集中在画面和边框。
- 电脑左侧是原创学习小屋与简短介绍，右侧是真实登录表单；去掉旧的宣传卡片网格和大面积玻璃渐变。注册关闭的说明放在提交区下方，入口仍隐藏。
- 手机使用单列、小型品牌与横向场景，不将电脑版整块缩成竖条；宽度320px起可用。较矮或横屏窗口隐藏场景，长注册表单使用整页自然滚动；输入字号16px。
- 邮箱验证码、账号密码、密码可见性、找回密码、已配置第三方、协议弹窗、发码/提交防重、原目标跳转保留。插画失败时回退为像素书本和短句，仍可登录。
- 页面不显示虚构在线人数、等级或学习统计；标题栏小方块为装饰，没有假关闭按钮。用户减少动态效果时取消控件转场。

实现：`web/src/views/auth/AuthView.vue`、`web/src/assets/styles/pixel-auth.css`、`web/src/components/PixelBookMark.vue`。

## 插画与来源

使用内置 **imagegen** 工具生成原创插画（没有使用CLI/API fallback）。项目最终素材保存于 `web/public/art/pixel-study-room.webp`，1448×1086，332,078字节。原始PNG保留在生成器目录；网站版本仅作WebP传输编码优化，没有裁剪、缩放或重新绘制内容。桌面与手机通过CSS分别展示场景，文字、输入框和按钮均为真实HTML。

最终生成提示词：

> Create an ORIGINAL production website decorative illustration for a Chinese exam-study app login screen. It is a cute chibi 16-bit PIXEL ART cozy study nook, a polished indie game background, NOT a UI mockup. Wide 4:3 landscape composition, high resolution but visibly hand placed crisp pixel clusters, consistent pixel scale, hard pixel edges, no outlines made of smooth vectors. Soft restrained palette: warm ivory, sage green, dusty peach, honey wooden desk, teal shadow, gentle blue sky. Scene: one tiny adorable chibi young adult student with short dark hair and a sage cardigan sitting at a wooden desk, seen three-quarter from behind, reading an open textbook. A small round mint companion resting at the side of the desk subtly suggests an AI study buddy. A round warm desk lamp, a few stacked books, small mug, one leafy houseplant. On the left, a large square-paned window shows peaceful trees, pale clouds and distant modest campus buildings, warm late-afternoon light. Peaceful optimistic thoughtful mood. Room vignette fills entire canvas with tasteful open areas, charming small details, professional pixel game environment art. Central lower middle focus on student/desk; main figures safely inside middle 70%, usable at smaller sizes and shallow mobile crop. No written text, no labels, no lettering, no logo, no watermark, no UI, no buttons, no counters, no large sparkles, no busy particles, no neon, no purple SaaS gradients, no photorealism, no 3D render, no smooth digital painting, no Gaussian blur. Make this feel genuinely inviting, cute and meticulously art-directed, like a quiet save room in a pixel adventure.

## 验证

前端254项/50文件完整回归通过，生产构建成功。原账号流程、注册开关、匿名拦截和10种登录有效宽度回归继续通过，新增插画失败后仍可密码登录用例。后端沿用190项已通过基线，本轮未改后端或迁移；GitHub CI按发布提交另行核对。

插画已人工查看原图，资产损坏/缺失可降级。本地预览的页面、组件、CSS与WebP分别验证HTTP返回。Tabbit稳定启动器未建立连接，尚未取得真实浏览器登录页截图；像素布局、软键盘和触控仍需实机检查，不以样式规则测试代替视觉验收。
