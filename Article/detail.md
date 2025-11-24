第一次部署成功，还是挺兴奋，赶紧记录一下成功部署的细节，不免后面又push不上了！

1、拥有一个github账号，这还是比拥有一个谷歌账号容易得多。需要记住账号的邮箱和用户名，后续会频繁用到。

2、下载git。打开[git官网下载页](https://git-scm.com/download/win)，下载适配的系统版本。注意安装包较大，可以移动到D盘，然后再双击打开。【避免C盘内存不够了】【我的是windows版本】

3、安装git。主要操作步骤是：弹出许可协议——选择安装路径（建议D盘）——选择组件（最好全选）——选择默认编辑器——设置Git命令的环境变量（Use Git from the Windows Command Prompt）——看到有main和master的去github上看一下用的那个——其他基本都是默认选项，有犹豫不决的就截图问ai即可，不会有太大差别。最后在终端输入 `git --version`验证一下是否安装成功。

4、配置git。需要打开git bash（管理员权限），输入两条命令，

```bash
git config --global user.name "你的GitHub用户名"
git config --global user.email "你的GitHub邮箱"
```

然后输入 `git config --global --list`验证配置是否成功。

5、GitHub准备。首先要新建仓库，仓库名必须是你的 `GitHub用户名.github.io`，否则无法部署成页面！然后选择公开，不要勾选创建README文件。描述可以不写，写了最终会展示在仓库中被大家看到。最后点击创建仓库。创建好仓库后记录仓库的地址。比如 `https://github.com/zhangsan/zhangsan.github.io.git`

6、创建访问令牌。登录GitHub，头像——设置——左侧开发者设置——个人访问令牌——tokens(classic)——生成新令牌——填写备注——有效期选择永不过期——权限只用勾选repo及其所有子项——点击生成令牌——看到一串绿色令牌字符串，复制下来保存到记事本！后续会用！

7、推送本地文件。首先打开git bash（管理员权限），目录设置为目标文件夹。输入 `git init` ，初始化成功后，输入 `git add .`，无报错后，输入 `git commit -m "首次部署博客"`（这个文字会显示在仓库中）。无报错后，输入 `git push -u origin main`（默认仓库分支要和github上一致）。推送过程中会弹出登录认证，填写令牌内容即可。若最后显示done等信息表明推送成功。此时刷新github页面会看到推送的文件！

8、处理 `git push`推送不成功的问题。这一步报错绝大概率是网络设置问题。我尝试多种办法，解决思路是：首先测试能否访问 `ping github.com`；其次用手机热点连接；然后关闭本地防火墙。【补充关键：用魔法】

9、开启GitHub Page。进入仓库——导航栏设置——pages选项——source选从分支部署——出现 `Your site is published at https:// 你的用户名.github.io/`即部署成功！
