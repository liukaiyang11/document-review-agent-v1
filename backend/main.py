"""
文档审核系统 - FastAPI 后端服务
支持票据审查和合同审查
"""

import os
import sys
import json
import uuid
import shutil
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
from fastapi import Form

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 添加项目根目录到路径（需要上两级目录才能找到 invoice_verification.py）
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

# 导入发票处理模块
from invoice_verification import InvoiceExtractionSystem, Invoice
from invoice_validation_agents import InvoiceValidationSystem, FinalValidationReport

# 导入合同审查模块
from contract_info_extraction import extract_contract_info_dict, ContractOverview

# ==================== 配置 ====================

# 创建必要的目录
UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# API 配置
API_KEY = os.getenv("DASHSCOPE_API_KEY", "")
BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"

# ==================== 数据模型 ====================

class OCRResponse(BaseModel):
    """OCR识别响应"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    invoice_id: Optional[str] = None


class ValidationRequest(BaseModel):
    """审查请求"""
    invoice_id: str
    invoice_data: Dict[str, Any]


class ValidationResponse(BaseModel):
    """审查响应"""
    success: bool
    message: str
    report: Optional[Dict[str, Any]] = None


# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="文档审核系统 API",
    description="支持票据和合同的OCR识别与智能审查",
    version="1.0.0"
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # React 开发服务器
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 初始化系统
extraction_system = None
validation_system = None

if API_KEY:
    try:
        extraction_system = InvoiceExtractionSystem(
            api_key=API_KEY,
            model_name="qwen3-vl-plus"
        )
        validation_system = InvoiceValidationSystem(
            api_key=API_KEY,
            enable_llm_validation=False  # 可设置为 True 启用 LLM 业务规则校验
        )
        print("发票识别和校验系统初始化成功")
    except Exception as e:
        print(f"⚠ 系统初始化警告: {e}")
else:
    print("⚠ 未设置 DASHSCOPE_API_KEY 环境变量")


# ==================== API 端点 ====================

@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "文档审核系统 API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "invoice_upload": "/api/invoice/upload",
            "invoice_validate": "/api/invoice/validate",
            "contract_overview": "/api/contract/overview",
            "health": "/api/health"
        }
    }


@app.get("/api/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "extraction_system": extraction_system is not None,
        "validation_system": validation_system is not None,
        "timestamp": datetime.now().isoformat()
    }


@app.post("/api/invoice/upload", response_model=OCRResponse)
async def upload_invoice(file: UploadFile = File(...)):
    """
    上传发票图片并进行OCR识别

    支持格式: PNG, JPG, JPEG, PDF
    """
    try:
        # 验证文件类型
        if not file.content_type or not file.content_type.startswith(('image/', 'application/pdf')):
            raise HTTPException(status_code=400, detail="不支持的文件类型,仅支持图片和PDF")

        # 验证文件大小 (20MB)
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="文件大小超过20MB限制")

        # 生成唯一文件名
        file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'png'
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = UPLOAD_DIR / unique_filename

        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # 检查系统是否初始化
        if not extraction_system:
            # 返回模拟数据用于测试
            return OCRResponse(
                success=True,
                message="OCR识别完成(测试模式)",
                data=_get_mock_invoice_data(),
                invoice_id=str(uuid.uuid4())
            )

        # 执行OCR识别
        print(f"正在识别发票: {file_path}")
        invoice = extraction_system.extract_from_image(str(file_path))

        # 转换为字典
        invoice_data = invoice.to_dict()

        return OCRResponse(
            success=True,
            message="发票识别成功",
            data=invoice_data,
            invoice_id=f"{invoice.invoice_code}_{invoice.invoice_number}"
        )

    except HTTPException:
        raise
    except ValidationError as e:
        print(f"发票数据验证失败: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail="暂不支持该文档类型，请上传正确的增值税发票图片"
        )
    except Exception as e:
        print(f"OCR识别错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"OCR识别失败: {str(e)}")


@app.post("/api/invoice/validate", response_model=ValidationResponse)
async def validate_invoice(request: ValidationRequest):
    """
    执行发票审查

    进行完整性、格式、计算和业务规则校验
    """
    try:
        invoice_data = request.invoice_data

        # 检查系统是否初始化
        if not validation_system:
            # 返回模拟审查结果
            return ValidationResponse(
                success=True,
                message="审查完成(测试模式)",
                report=_get_mock_validation_report(invoice_data)
            )

        # 执行校验
        print(f"正在审查发票: {request.invoice_id}")
        report = validation_system.validate_invoice(invoice_data)

        # 转换为字典
        report_data = report.model_dump(exclude_none=False)

        return ValidationResponse(
            success=True,
            message="发票审查完成",
            report=report_data
        )

    except Exception as e:
        print(f"审查错误: {str(e)}")
        raise HTTPException(status_code=500, detail=f"审查失败: {str(e)}")


# ==================== 模拟数据(用于测试) ====================

def _get_mock_invoice_data() -> Dict[str, Any]:
    """获取模拟发票数据"""
    return {
        "invoice_type": "增值税专用发票",
        "province": "上海",
        "invoice_code": "3100153130",
        "invoice_number": "14641426",
        "issue_date": "2016-06-02",
        "check_code": "",
        "purchaser_name": "百度时代网络技术(北京)有限公司",
        "purchaser_tax_id": "110108787751579",
        "purchaser_address": "北京市海淀区上地十街10号 010-59928888",
        "purchaser_bank": "招商银行股份有限公司北京上地支行 110920357610301",
        "seller_name": "上海爱信诺航天信息有限公司",
        "seller_tax_id": "310115687812026",
        "seller_address": "上海市浦东新区龙阳路2345号 021-50277777",
        "seller_bank": "中国工商银行上海市杨浦支行 1001241019000053363",
        "total_amount": 12580.00,
        "total_tax": 754.80,
        "total_amount_with_tax": 13334.80,
        "amount_in_words": "壹万叁仟叁佰叁拾肆元捌角整",
        "line_items": [
            {
                "row": "1",
                "name": "*信息技术服务*技术服务费",
                "specification": None,
                "unit": None,
                "quantity": None,
                "unit_price": None,
                "amount": 12580.00,
                "tax_rate": 0.06,
                "tax_amount": 754.80
            }
        ],
        "payee": "张三",
        "checker": "李四",
        "drawer": "王五",
        "remarks": ""
    }


def _get_mock_validation_report(invoice_data: Dict[str, Any]) -> Dict[str, Any]:
    """获取模拟审查报告"""
    return {
        "invoice_id": f"{invoice_data.get('invoice_code', 'N/A')}_{invoice_data.get('invoice_number', 'N/A')}",
        "validation_time": datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        "overall_status": "PASSED",
        "summary": "发票校验完全通过,未发现任何问题",
        "agent_reports": [
            {
                "agent_name": "完整性校验Agent",
                "execution_time": 0.05,
                "results": [
                    {
                        "agent_name": "完整性校验Agent",
                        "level": "info",
                        "category": "完整性校验",
                        "message": "所有 13 个必填字段完整",
                        "field": None,
                        "expected": None,
                        "actual": None,
                        "suggestion": "专用发票核心信息齐全"
                    }
                ]
            },
            {
                "agent_name": "格式校验Agent",
                "execution_time": 0.03,
                "results": [
                    {
                        "agent_name": "格式校验Agent",
                        "level": "info",
                        "category": "格式校验",
                        "message": "发票代码格式正确",
                        "field": "invoice_code",
                        "expected": None,
                        "actual": invoice_data.get('invoice_code'),
                        "suggestion": None
                    },
                    {
                        "agent_name": "格式校验Agent",
                        "level": "info",
                        "category": "格式校验",
                        "message": "发票号码格式正确",
                        "field": "invoice_number",
                        "expected": None,
                        "actual": invoice_data.get('invoice_number'),
                        "suggestion": None
                    }
                ]
            },
            {
                "agent_name": "计算校验Agent",
                "execution_time": 0.02,
                "results": [
                    {
                        "agent_name": "计算校验Agent",
                        "level": "info",
                        "category": "计算校验",
                        "message": f"价税合计计算正确: {invoice_data.get('total_amount', 0):.2f} + {invoice_data.get('total_tax', 0):.2f} = {invoice_data.get('total_amount_with_tax', 0):.2f}",
                        "field": "total_amount_with_tax",
                        "expected": None,
                        "actual": None,
                        "suggestion": None
                    }
                ]
            },
            {
                "agent_name": "业务规则校验Agent",
                "execution_time": 0.01,
                "results": [
                    {
                        "agent_name": "业务规则校验Agent",
                        "level": "info",
                        "category": "业务规则校验",
                        "message": "未发现明显的业务逻辑问题",
                        "field": None,
                        "expected": None,
                        "actual": None,
                        "suggestion": None
                    }
                ]
            }
        ]
    }


# ==================== 合同审查 API ====================

class ContractOverviewResponse(BaseModel):
    """合同概览响应"""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


@app.post("/api/contract/overview", response_model=ContractOverviewResponse)
async def get_contract_overview(file: UploadFile = File(...)):
    """
    上传合同PDF/图片并提取概览信息

    提取内容：甲方、乙方、合同金额、日期等关键信息
    支持格式: PDF, PNG, JPG, JPEG
    """
    try:
        # 验证文件类型
        if not file.content_type or not file.content_type.startswith(('image/', 'application/pdf')):
            raise HTTPException(status_code=400, detail="不支持的文件类型,仅支持图片和PDF")

        # 验证文件大小 (20MB)
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > 20 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="文件大小超过20MB限制")

        # 生成唯一文件名
        file_ext = file.filename.split('.')[-1] if '.' in file.filename else 'pdf'
        unique_filename = f"{uuid.uuid4()}.{file_ext}"
        file_path = UPLOAD_DIR / unique_filename

        # 保存文件
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        print(f"正在提取合同信息: {file_path}")

        # 如果不是PDF，暂时不支持
        if not file.content_type == 'application/pdf':
            raise HTTPException(
                status_code=400,
                detail="目前仅支持PDF格式的合同文件"
            )

        try:
            # 步骤1: 使用 MinerU 解析 PDF
            print(f"  步骤1: 调用 MinerU 解析 PDF...")
            import requests
            import json as json_lib

            MINERU_API_URL = os.getenv("MINERU_API_URL", "http://localhost:8080/parse")
            VLLM_SERVER_URL = os.getenv("VLLM_SERVER_URL", "")

            with open(file_path, "rb") as f:
                files = [("files", (file.filename, f, "application/pdf"))]
                data = {
                    "backend": "pipeline",
                    "server_url": VLLM_SERVER_URL,
                    "parse_method": "auto",
                    "lang_list": "ch",
                    "return_md": "true",
                    "return_content_list": "true",
                    "start_page_id": "0",
                    "end_page_id": "99999",
                }

                response = requests.post(MINERU_API_URL, files=files, data=data, timeout=600)
                response.raise_for_status()

            mineru_result = response.json()
            print(f"  MinerU 解析完成")

            # 提取文本内容
            if "results" in mineru_result:
                result_key = list(mineru_result["results"].keys())[0]
                result = mineru_result["results"][result_key]
                md_content = result.get("md_content", "")
            else:
                md_content = mineru_result.get("md_content", "")

            if not md_content:
                raise ValueError("MinerU 解析结果为空")

            print(f"  提取到文本长度: {len(md_content)} 字符")

            # 步骤2: 使用 LLM 提取合同信息
            print(f"  步骤2: 调用 LLM 提取合同信息...")
            overview = extract_contract_info_dict(md_content)
            print(f"  信息提取完成")

            # 打印提取的数据，方便调试
            print(f"\n提取的合同数据:")
            print(f"  合同类型: {overview.get('contract_type', '')}")
            print(f"  合同标题: {overview.get('contract_title', '')}")
            print(f"  甲方: {overview.get('party_a', '')}")
            print(f"  乙方: {overview.get('party_b', '')}")
            print(f"  金额: {overview.get('total_amount', '')}")
            print(f"  生效日期: {overview.get('effective_date', '')}")
            print(f"  到期日期: {overview.get('expiry_date', '')}")
            print(f"  关键条款数量: {len(overview.get('key_terms', []))}")
            print()

            # 步骤3: 保存markdown内容供审查使用
            # 生成合同ID（使用文件名的stem作为ID）
            contract_id = file_path.stem
            md_file = UPLOAD_DIR / f"{contract_id}_content.md"

            print(f"  步骤3: 保存合同内容到 {md_file}")
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(md_content)

            # 在响应中添加contract_id
            overview["contract_id"] = contract_id

            return ContractOverviewResponse(
                success=True,
                message="合同信息提取成功",
                data=overview
            )

        except requests.exceptions.ConnectionError:
            print(f"  ❌ 无法连接到 MinerU API: {MINERU_API_URL}")
            raise HTTPException(
                status_code=503,
                detail=f"无法连接到 MinerU 服务，请确保服务运行在 {MINERU_API_URL}"
            )
        except requests.exceptions.Timeout:
            print(f"  ❌ MinerU API 请求超时")
            raise HTTPException(
                status_code=504,
                detail="PDF 解析超时，请稍后重试"
            )
        except ValueError as e:
            print(f"  ❌ 数据处理错误: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"数据处理失败: {str(e)}"
            )
        except Exception as e:
            print(f"  ❌ 提取失败: {e}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"合同信息提取失败: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        print(f"合同信息提取错误: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"信息提取失败: {str(e)}")


@app.post("/api/contract/audit")
async def audit_contract(contract_id: str = Form(...)):
    """
    合同专业审查接口

    接收合同ID，从上传记录中获取合同内容，然后调用LLM进行专业审查
    """
    print(f"\n{'='*80}")
    print(f"开始合同专业审查")
    print(f"{'='*80}")
    print(f"合同ID: {contract_id}")

    try:
        # 1. 从上传记录中获取合同的markdown内容
        md_file = UPLOAD_DIR / f"{contract_id}_content.md"

        if not md_file.exists():
            raise HTTPException(
                status_code=404,
                detail=f"未找到合同内容文件: {contract_id}"
            )

        # 读取合同markdown内容
        with open(md_file, "r", encoding="utf-8") as f:
            contract_text = f.read()

        print(f"  合同文本长度: {len(contract_text)} 字符")

        # 2. 调用专业审查系统
        print(f"  步骤1: 调用LLM进行专业审查...")

        from langchain_openai import ChatOpenAI
        from langchain_core.prompts import ChatPromptTemplate
        from pydantic import BaseModel, Field, ConfigDict
        from typing import List

        # 导入审查规则和提示词
        import sys
        sys.path.append('./07_DocumentReviewAgent')
        from contract_audit_prompt_professional import (
            PROFESSIONAL_CONTRACT_AUDIT_RULES,
            PROFESSIONAL_SYSTEM_PROMPT,
            PROFESSIONAL_USER_PROMPT
        )

        # 定义数据结构
        class Issue(BaseModel):
            model_config = ConfigDict(populate_by_name=True, extra='allow')
            rule_category: str = Field(description="规则类别")
            issue_type: str = Field(description="问题类型")
            description: str = Field(description="问题详细描述")
            original: str = Field(default="", description="原文中有问题的部分")
            suggestion: str = Field(default="", description="修改建议")
            severity: str = Field(
                description="严重程度: high, medium, low",
                pattern="^(high|medium|low)$"
            )
            legal_risk: str = Field(default="", description="法律风险说明")

        class ModificationMapping(BaseModel):
            model_config = ConfigDict(populate_by_name=True, extra='allow')
            original: str = Field(default="", description="原文片段")
            modified: str = Field(default="", description="修改后的文本")
            reason: str = Field(default="", description="修改原因")
            rule_ref: str = Field(default="", description="规则编号")

        class AuditResult(BaseModel):
            has_issues: bool = Field(description="是否发现问题")
            issues: List[Issue] = Field(description="问题列表", default_factory=list)
            modifications: List[ModificationMapping] = Field(
                description="修改记录",
                default_factory=list
            )
            corrected_text: str = Field(description="修正后的完整文本")
            summary: str = Field(description="审核总结")
            overall_risk_level: str = Field(
                description="整体风险等级",
                pattern="^(high|medium|low|none)$"
            )

        # 创建LLM
        api_key = os.getenv("OPENAI_API_KEY")
        base_url = os.getenv("OPENAI_BASE_URL", "https://dashscope.aliyuncs.com/compatible-mode/v1")

        llm = ChatOpenAI(
            model="qwen-plus",
            temperature=0.1,
            max_tokens=6000,
            openai_api_key=api_key,
            openai_api_base=base_url
        )

        # 创建审查链
        audit_prompt = ChatPromptTemplate.from_messages([
            ("system", PROFESSIONAL_SYSTEM_PROMPT),
            ("user", PROFESSIONAL_USER_PROMPT)
        ])

        structured_llm = llm.with_structured_output(AuditResult)
        audit_chain = audit_prompt | structured_llm

        # 执行审查
        result = audit_chain.invoke({
            "rules": PROFESSIONAL_CONTRACT_AUDIT_RULES,
            "text": contract_text
        })

        print(f"  审查完成")
        print(f"  是否发现问题: {result.has_issues}")
        print(f"  问题总数: {len(result.issues)}")
        print(f"  整体风险等级: {result.overall_risk_level}")

        # 3. 转换为响应格式
        issues_data = []
        for issue in result.issues:
            issues_data.append({
                "rule_category": issue.rule_category,
                "issue_type": issue.issue_type,
                "description": issue.description,
                "original": issue.original,
                "suggestion": issue.suggestion,
                "severity": issue.severity,
                "legal_risk": issue.legal_risk
            })

        response_data = {
            "has_issues": result.has_issues,
            "issues": issues_data,
            "summary": result.summary,
            "overall_risk_level": result.overall_risk_level,
            "corrected_text": result.corrected_text
        }

        return {
            "success": True,
            "message": "审查完成",
            "data": response_data
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"  ❌ 审查失败: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"合同审查失败: {str(e)}"
        )


def _get_mock_contract_overview() -> Dict[str, Any]:
    """获取模拟合同概览数据"""
    return {
        "contract_type": "劳动合同",
        "contract_title": "劳动合同",
        "party_a": "北京某某科技有限公司",
        "party_a_type": "公司",
        "party_a_details": "统一社会信用代码：91110000XXXXXXXXXX，地址：北京市海淀区中关村大街1号",
        "party_b": "张三",
        "party_b_type": "个人",
        "party_b_details": "身份证号：110101199001011234",
        "total_amount": "月工资 ¥5,000",
        "amount_in_words": "人民币伍仟元整",
        "currency": "人民币",
        "effective_date": "2024年1月1日",
        "expiry_date": "2027年12月31日",
        "duration": "三年",
        "signing_date": "2024年1月1日",
        "key_terms": [
            "工资待遇：月工资人民币伍仟元整（¥5,000）",
            "支付方式：每月15日前银行转账",
            "合同期限：2024年1月1日至2027年12月31日",
            "违约责任：甲方未按时支付工资应支付违约金"
        ],
        "special_clauses": ""
    }


# ==================== 启动配置 ====================

if __name__ == "__main__":
    import uvicorn

    print("\n" + "="*60)
    print("文档审核系统 - FastAPI 后端服务")
    print("="*60)
    print(f"上传目录: {UPLOAD_DIR.absolute()}")
    print(f"API密钥状态: {'✓ 已配置' if API_KEY else '✗ 未配置 (将使用测试模式)'}")
    print("="*60 + "\n")

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
