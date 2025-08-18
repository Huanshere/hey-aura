# Babel 国际化快速操作指南

## 初始化翻译系统

### 1. 提取所有需要翻译的消息
```bash
pybabel extract -F babel.cfg -o locales/messages.pot .
```

## 添加新语言

```bash
# 添加中文
pybabel init -i locales/messages.pot -d locales -l zh
```

## 更新现有翻译

### 1. 重新提取消息并批量更新所有语言
```bash
pybabel extract -F babel.cfg -o locales/messages.pot .
pybabel update -i locales/messages.pot -d locales
```

### 2. 编辑翻译内容
打开对应的 `.po` 文件 让 cursor 帮忙改吧

### 3. 编译翻译文件
```bash
pybabel compile -d locales
```