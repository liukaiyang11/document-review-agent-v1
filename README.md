# Document Review Agent v1.0

> 基于 LangChain v1.0 搭建的文档审核 Agent，支持财务票据识别、合同合规审核等多场景文档自动审核。

[![Python](https://img.shields.io/badge/Python-3.10+-blue)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-v1.0-green)](https://www.langchain.com/)
[![React](https://img.shields.io/badge/React-18+-61dafb)](https://react.dev/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688)](https://fastapi.tiangolo.com/)
[![TailwindCSS](https://img.shields.io/badge/TailwindCSS-3+-06b6d4)](https://tailwindcss.com/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## ✨ 特性

- 🧾 **票据审核**：增值税发票自动识别与校验
- 📋 **合同审核**：法务合同合规性自动审查
- 🎯 **可配置规则**：灵活配置审核规则，适配不同业务场景
- 💬 **Agent 驱动**：基于 LangChain Agent 的智能审核流程
- 📊 **审核报告**：自动生成结构化审核报告
- 🎨 **现代界面**：React + Vite + TailwindCSS 构建

---

## 🏗️ 技术架构

```
┌───────────────────────────────────────────────────┐
│                    Frontend                       │
│           (React + Vite + TailwindCSS)            │
│  ┌──────────┐ ┌───────────┐ ┌─────────────────┐  │
│  │ 文件上传 │ │ 审核配置  │ │ 审核结果报告     │  │
│  └──────────┘ └───────────┘ └─────────────────┘  │
└───────────────────────┬───────────────────────────┘
                        │
            ┌───────────▼────────────┐
            │        Backend         │
            │       (FastAPI)        │
            │  ┌───────────────────┐ │
            │  │ Document Review   │ │  LangChain v1.0
            │  │  Agent            │ │
            │  └───────────────────┘ │
            │  ┌───────────────────┐ │
            │  │  规则引擎         │ │  可配置审核规则
            │  └───────────────────┘ │
            └────────────────────────┘
```

---

## 📁 项目结构

```
.
├── backend/                    # 后端服务
│   ├── main.py                 # API 入口
│   ├── requirements.txt
│   └── .env.example
├── frontend/                   # 前端
│   ├── src/
│   ├── package.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   ├── QUICKSTART.md
│   └── README.md
├── DEPLOYMENT_GUIDE.md         # 部署指南
└── README.md
```

---

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Node.js 18+
- 大模型 API Key（支持 OpenAI / 通义 / 豆包等）

### 后端启动

```bash
cd backend

# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
# 填入 API Key 等配置

# 启动服务
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 前端启动

```bash
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

访问 http://localhost:3000

### 部署

详细部署说明请参考 [DEPLOYMENT_GUIDE.md](DEPLOYMENT_GUIDE.md)。

---

## 📚 相关课程

- 📖 课程文档：[飞书知识库](#)（待补充）
- 🎥 视频教程：[课程链接](#)（待补充）

---

## 📄 License

MIT License - see [LICENSE](LICENSE) for details.
