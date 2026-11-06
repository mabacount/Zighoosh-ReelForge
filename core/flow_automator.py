"""
Zighoosh ReelForge - Google Flow Automation Bridge (Step 3)
Interacts with google-flow-cli over Chrome DevTools Protocol (CDP)
for native, non-robotic Google Flow generation.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class FlowAutomator:
    """
    پل ارتباطی ترمینال پایتون با google-flow-cli از طریق Chrome DevTools Protocol (CDP).
    """

    PLAN_FOLDER_MAP = {
        1: "Plan_01_Hook_Avatar",
        2: "Plan_02_Problem",
        3: "Plan_03_Company_Intro",
        4: "Plan_04_Requirements",
        5: "Plan_05_Benefits",
        6: "Plan_06_CTA_Avatar",
    }

    def __init__(self, config: Dict[str, Any], log_callback: Optional[Callable[[str], None]] = None):
        self.config = config.get("flow_config", {})
        self.timeout = max(int(self.config.get("generation_timeout_sec", 300)), 120)
        self.log = log_callback or print

    def _run_cli(self, args: list[str], cwd: Optional[Path] = None, timeout: int = 60) -> Dict[str, Any]:
        """اجرای امن دستورات flow در ترمینال و برگرداندن خروجی ساختاریافته."""
        flow_bin = shutil.which("flow") or "flow"
        cmd = [flow_bin] + args
        self.log(f"💻 اجرای دستور: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
                shell=(shutil.which("flow") is None or os.name == "nt"),  # برای سازگاری کامل با Windows CMD/PowerShell
            )
            stdout_clean = result.stdout.strip()
            if stdout_clean:
                try:
                    return {"ok": result.returncode == 0, "data": json.loads(stdout_clean), "raw": stdout_clean}
                except json.JSONDecodeError:
                    s = stdout_clean.find("{")
                    e = stdout_clean.rfind("}")
                    if s != -1 and e != -1 and e > s:
                        try:
                            return {"ok": result.returncode == 0, "data": json.loads(stdout_clean[s:e+1]), "raw": stdout_clean}
                        except json.JSONDecodeError:
                            pass
                    return {"ok": result.returncode == 0, "data": {}, "raw": stdout_clean}
            return {"ok": result.returncode == 0, "data": {}, "raw": result.stderr.strip()}
        except subprocess.TimeoutExpired:
            self.log("❌ خطای Timeout در اجرای دستور ترمینال Google Flow.")
            return {"ok": False, "error": "TIMEOUT", "data": {}}
        except Exception as e:
            self.log(f"❌ خطا در اجرای CLI: {e}")
            return {"ok": False, "error": str(e), "data": {}}

    def launch_chrome(self) -> bool:
        """
        گام اول: اجرای مرورگر کروم بومی روی پورت 9222 برای لاگین بدون پرچم رباتیک.
        دستور معادل: flow launch
        """
        self.log("🌐 در حال باز کردن مرورگر Google Chrome (پورت CDP 9222)...")
        res = self._run_cli(["launch"], timeout=30)
        if res["ok"]:
            self.log("✅ مرورگر کروم باز شد. اگر لاگین نیستید، در پنجره بازشده وارد اکانت گوگل شوید.")
        return res["ok"]

    def run_diagnostics(self) -> Dict[str, Any]:
        """
        بررسی وضعیت پورت CDP، نصب بودن Playwright و لاگین بودن اکانت گوگل.
        دستور معادل: flow doctor --json
        """
        self.log("🩺 در حال بررسی وضعیت اتصال به Google Flow (flow doctor)...")
        res = self._run_cli(["doctor", "--json"], timeout=30)
        data = res.get("data", {})
        cdp_open = data.get("cdpOpen", False)
        auth_ok = data.get("googleAuthenticated", False)

        if cdp_open and auth_ok:
            self.log("✅ اتصال برقرار است: پورت 9222 باز و اکانت گوگل لاگین است.")
        elif not cdp_open:
            self.log("⚠️ پورت 9222 کروم بسته است. ابتدا دکمه «باز کردن کروم (flow launch)» را بزنید.")
        elif not auth_ok:
            self.log("⚠️ مرورگر باز است اما وارد حساب گوگل نشده‌اید. لطفاً در پنجره کروم لاگین کنید.")

        return {
            "ok": res["ok"] and cdp_open and auth_ok,
            "cdpOpen": cdp_open,
            "playwright": data.get("playwright", False),
            "googleAuthenticated": auth_ok,
            "projectId": data.get("projectId"),
            "raw": res.get("raw", "")
        }

    def generate_thumbnail_bg(self, project_root: Path, bg_prompt: str, model: str = "Nano Banana Pro") -> bool:
        """
        تولید تصویر پس‌زمینه تامنیل (9:16) و ذخیره مستقیم در پوشه Audio_BGM/AI_Background.png.
        """
        output_file = project_root / "03_Raw_DropZone" / "Audio_BGM" / "AI_Background.png"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        self.log(f"🖼 در حال تولید تصویر پس‌زمینه تامنیل با مدل {model}...")
        args = [
            "scene",
            "--media", "image",
            "-p", bg_prompt,
            "-M", model,
            "--aspect", "9:16",
            "--generate",
            "-w",
            "-t", str(self.timeout),
            "-o", str(output_file),
            "--json"
        ]
        res = self._run_cli(args, cwd=project_root, timeout=self.timeout + 30)
        if res["ok"] and output_file.exists():
            self.log(f"✅ تصویر تامنیل با موفقیت ذخیره شد: {output_file.name}")
            return True
        self.log("❌ خطا در تولید یا دانلود تصویر پس‌زمینه تامنیل.")
        return False

    def generate_plan_video(
        self,
        project_root: Path,
        plan_number: int,
        prompt: str,
        model: str = "Veo 3.1 - Fast",
        duration: str = "8s"
    ) -> bool:
        """
        تولید ویدیوی یک پلان مشخص (۱ تا ۶) و دانلود مستقیم آن در پوشه مربوطه در 03_Raw_DropZone.
        """
        folder_name = self.PLAN_FOLDER_MAP.get(plan_number, f"Plan_0{plan_number}")
        output_file = project_root / "03_Raw_DropZone" / folder_name / f"V_Plan_0{plan_number}.mp4"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        self.log(f"🎬 در حال تولید ویدیوی پلان {plan_number} با مدل {model}...")
        args = [
            "scene",
            "--media", "video",
            "-p", prompt,
            "-M", model,
            "--aspect", "9:16",
            "--duration", duration,
            "--generate",
            "-w",
            "-t", str(self.timeout),
            "-o", str(output_file),
            "--json"
        ]
        res = self._run_cli(args, cwd=project_root, timeout=self.timeout + 60)
        if res["ok"] and output_file.exists():
            self.log(f"✅ ویدیوی پلان {plan_number} با موفقیت دانلود شد: {output_file.name}")
            return True
        self.log(f"❌ خطا در تولید ویدیوی پلان {plan_number}.")
        return False

    def run_declarative_pipeline(self, project_root: Path, dry_run: bool = False) -> bool:
        """
        اجرای کامل فایل 02_AI_Brain_JSON/flow.json با دستور flow run.
        """
        ai_brain_dir = project_root / "02_AI_Brain_JSON"
        flow_json_path = ai_brain_dir / "flow.json"
        if not flow_json_path.exists():
            self.log("❌ فایل flow.json در پوشه 02_AI_Brain_JSON یافت نشد.")
            return False

        args = ["run", "--json"]
        if dry_run:
            args.insert(1, "--dry-run")
            self.log("🧪 در حال اجرای آزمایشی پایپلاین (Dry Run - بدون مصرف کردیت)...")
        else:
            self.log("🚀 شروع اجرای خودکار کل صحنه‌ها در Google Flow...")

        res = self._run_cli(args, cwd=ai_brain_dir, timeout=(self.timeout * 6) + 120)
        if res["ok"]:
            self.log("✅ اجرای پایپلاین flow.json با موفقیت به پایان رسید.")
            return True
        self.log("❌ اجرای پایپلاین با خطا مواجه شد. جزئیات را در لاگ بررسی کنید.")
        return False
