from __future__ import annotations

from app import db


def get_user_firm_name(user_id: int | None) -> str:
    if not user_id:
        return "Tanımlı Değil"
    try:
        user = db.get_user_by_id(int(user_id))
    except Exception:
        user = None
    if not user:
        return "Tanımlı Değil"
    company_name = user["company_name"] if "company_name" in user.keys() else None
    return str(company_name).strip() if company_name else "Tanımlı Değil"


def get_active_user_firm_name(current_user) -> str:
    if not current_user:
        return "Tanımlı Değil"
    try:
        company_name = current_user["company_name"]
    except Exception:
        company_name = current_user.get("company_name") if isinstance(current_user, dict) else None
    if company_name:
        text = str(company_name).strip()
        if text:
            return text
    try:
        user_id = current_user["id"]
    except Exception:
        user_id = current_user.get("id") if isinstance(current_user, dict) else None
    return get_user_firm_name(int(user_id)) if user_id else "Tanımlı Değil"

def get_user_sidebar_meta(user: dict) -> str:
    """Kullanıcı için sidebar'da gösterilecek şirket/şube bilgisini üretir."""
    role_codes = {part.strip() for part in (user.get("role_codes") or "").split(",") if part.strip()}
    if "admin" in role_codes:
        return "Admin"

    company_names = [p.strip() for p in (user.get("company_names") or "").split(",") if p.strip()]
    company_codes = [p.strip() for p in (user.get("company_codes") or "").split(",") if p.strip()]
    branch_names = [p.strip() for p in (user.get("branch_names") or "").split(",") if p.strip()]
    
    if user.get("company_name") and user.get("branch_name"):
        return f"{user['company_name']} / {user['branch_name']}"
    
    if company_names and branch_names and len(company_names) == 1:
        return f"{company_names[0]} / {branch_names[0]}"
        
    if company_names:
        meta = ", ".join(company_codes[:2] or company_names[:2])
        return meta + (f" +{len(company_names) - 2}" if len(company_names) > 2 else "")
        
    if branch_names:
        meta = ", ".join(branch_names[:2])
        return meta + (f" +{len(branch_names) - 2}" if len(branch_names) > 2 else "")
        
    return ""
