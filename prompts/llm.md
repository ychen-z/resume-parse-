输出格式：

1. 按照JSON格式输出, JSON中不要包含注释，不要包含任何XML标签，不要markdown格式；
2. 如果未提取到相关信息则返回null;
3. 如果列表下子字段为空则列表字段返回null；

注意：

1. 描述、职责等长文本保留换行和排序；
2. 所有字段取值必须完全基于上下文文本，勿作任何推理；
3. 高频重复出现的姓名为水印信息，勿当做候选人姓名；
4. 若不存在单独的项目经历模块，则无需提炼项目经历；工作经历模块下的所有内容都应属于工作经历；5.人选玩过的游戏经历勿当做人选的工作经历或者项目经历，应过滤掉这部分的内容；6.人选写简历的方式不一样，。

字段枚举code：

- 1.学历：string '05'-大专 '06'-本科 '07'-硕士 '09'-MBA '10'-博士 '00'-其他
- 2.工作性质：number 0-全职 1-实习 2-兼职
- 3.是否全日制：number 1-是，0-否

请从中解析后txt中提取关键信息：

1.基础简历信息(resumeBase)：
姓名：applicantName
手机号：mobile (不保留区号)
邮箱: email

2.教育经历(resumeEducationList)：
开始时间: startDate
结束时间: endDate
学校名称: schoolName
专业名称: majorName
学历: degree (必须按照枚举code返回)
是否全日制：fullTime (必须按照枚举code返回)

3.项目经历(resumeProjectList)：
开始时间: startDate
结束时间: endDate
项目名称: name
项目描述：description
项目职责：duty

4.工作经历(resumeWorkExpList):
开始时间: startDate
结束时间: endDate
公司名称：company
职位：position
工作职责：duty
工作性质：workType (未十分明确则返回null，有值则必须按照枚举code返回)
