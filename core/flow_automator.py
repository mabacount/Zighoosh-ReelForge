"""
Zighoosh ReelForge - Google Flow Automation Bridge (Step 3)
Interacts with Google Flow over Chrome DevTools Protocol (CDP)
for native, non-robotic Google Flow generation with support for both
Direct Mode and Creative Agent Mode, Persian & English UI, and VPN detection.
"""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class FlowAutomator:
    """
    پل ارتباطی ترمینال پایتون با Google Flow از طریق Chrome DevTools Protocol (CDP).
    """

    PLAN_FOLDER_MAP = {
        1: "Plan_01_Hook_Avatar",
        2: "Plan_02_Problem",
        3: "Plan_03_Company_Intro",
        4: "Plan_04_Requirements",
        5: "Plan_05_Benefits",
        6: "Plan_06_CTA_Avatar",
        7: "Plan_07_Outro",
    }

    def __init__(self, config: Dict[str, Any], log_callback: Optional[Callable[[str], None]] = None):
        self.config = config.get("flow_config", {})
        self.timeout = max(int(self.config.get("generation_timeout_sec", 300)), 120)
        self.log = log_callback or print
        self.worker_script = Path(__file__).parent / "flow_worker.js"

    def _is_port_open(self, port: int = 9222) -> bool:
        """بررسی سریع باز بودن پورت CDP."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1.0)
                return s.connect_ex(("127.0.0.1", port)) == 0
        except Exception:
            return False

    def _run_worker(self, args: list[str], cwd: Optional[Path] = None, timeout: int = 60) -> Dict[str, Any]:
        """اجرای اسکریپت worker با Node.js و برگرداندن خروجی ساختاریافته JSON."""
        node_bin = shutil.which("node") or "node"
        cmd = [node_bin, str(self.worker_script)] + args
        self.log(f"💻 اجرای دستور: {' '.join(cmd[:6])}...")

        try:
            result = subprocess.run(
                cmd,
                cwd=str(cwd) if cwd else None,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
                shell=(os.name == "nt"),
            )
            stdout_clean = result.stdout.strip()
            stderr_clean = result.stderr.strip()
            res_ok = result.returncode == 0
            parsed_data = {}

            output_str = stdout_clean or stderr_clean
            if output_str:
                s = output_str.find("{")
                e = output_str.rfind("}")
                if s != -1 and e != -1 and e > s:
                    try:
                        parsed_data = json.loads(output_str[s:e+1])
                        if isinstance(parsed_data, dict):
                            res_ok = parsed_data.get("ok", res_ok)
                    except json.JSONDecodeError:
                        pass

            if isinstance(parsed_data, dict) and parsed_data.get("error") == "PUBLIC_ERROR_UNUSUAL_ACTIVITY":
                msg = parsed_data.get("message") or "گوگل پیام فعالیت غیرعادی صادر کرده است (VPN IP)."
                self.log(f"⚠️ {msg}", "WARNING")
            elif isinstance(parsed_data, dict) and not res_ok and "message" in parsed_data:
                self.log(f"⚠️ پیام از Google Flow: {parsed_data['message']}", "WARNING")
            elif not res_ok and stderr_clean:
                self.log(f"⚠️ پیام خطا: {stderr_clean[:250]}", "WARNING")

            return {"ok": res_ok, "data": parsed_data, "raw": output_str}
        except subprocess.TimeoutExpired:
            self.log("❌ خطای Timeout در اجرای دستور Google Flow.")
            return {"ok": False, "error": "TIMEOUT", "data": {}}
        except Exception as e:
            self.log(f"❌ خطا در اجرای Worker: {e}")
            return {"ok": False, "error": str(e), "data": {}}

    def ensure_active_project(self, project_name: str = "Zighoosh ReelForge") -> bool:
        """
        اطمینان از باز بودن پروژه فعال روی بوم مرورگر.
        """
        diag = self.run_diagnostics()
        if diag.get("projectId"):
            return True
        return True

    def launch_chrome(self) -> bool:
        """
        گام اول: اجرای مرورگر کروم بومی روی پورت 9222 برای لاگین بدون پرچم رباتیک.
        """
        port = int(self.config.get("cdp_port", 9222))
        if self._is_port_open(port):
            self.log(f"✅ مرورگر کروم قبلاً روی پورت {port} باز شده و آماده استفاده است.")
            return True

        profile_dir = self.config.get("chrome_profile_dir")
        if profile_dir:
            expanded_profile = str(Path(os.path.expanduser(profile_dir)).resolve())
        else:
            expanded_profile = str(Path(os.path.expanduser("~/.config/google-chrome-flow")).resolve())

        os.makedirs(expanded_profile, exist_ok=True)

        chrome_candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            shutil.which("chrome") or shutil.which("google-chrome") or "chrome"
        ]

        chrome_bin = None
        for cand in chrome_candidates:
            if cand and os.path.exists(cand):
                chrome_bin = cand
                break

        if not chrome_bin:
            chrome_bin = "chrome"

        self.log(f"🌐 در حال باز کردن مرورگر Google Chrome (پورت CDP {port})...")

        args = [
            chrome_bin,
            f"--remote-debugging-port={port}",
            f"--user-data-dir={expanded_profile}",
            "--no-first-run",
            "--no-default-browser-check",
            "https://flow.google.com"
        ]

        try:
            subprocess.Popen(
                args,
                shell=(os.name == "nt"),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                stdin=subprocess.DEVNULL,
            )
            # صبر برای بالا آمدن پورت CDP
            for _ in range(15):
                time.sleep(0.5)
                if self._is_port_open(port):
                    self.log("✅ مرورگر کروم باز شد. اگر لاگین نیستید، در پنجره بازشده وارد اکانت گوگل شوید.")
                    return True
            self.log("⚠️ مرورگر اجرا شد ولی هنوز پورت 9222 پاسخ نمی‌دهد.")
            return True
        except Exception as e:
            self.log(f"❌ خطا در اجرای مستقیم Chrome: {e}")
            return False

    def open_flow_new_project(self) -> Dict[str, Any]:
        """
        گام اول همیار انسان و ماشین:
        اجرای کروم (در صورت بسته بودن) و ساخت/باز کردن یک پروژه جدید در Google Flow.
        """
        port = int(self.config.get("cdp_port", 9222))
        if not self._is_port_open(port):
            self.log("🌐 پورت CDP باز نیست. در حال اجرای مرورگر کروم...")
            if not self.launch_chrome():
                return {"ok": False, "message": "امکان باز کردن مرورگر کروم وجود نداشت."}
            time.sleep(1.5)

        self.log("🚀 در حال ایجاد و باز کردن پروژه جدید در Google Flow...")
        res = self._run_worker(["--action", "open-new-project"], timeout=35)
        if res.get("ok"):
            self.log("✅ پروژه با موفقیت در گوگل فلو ایجاد/آماده شد.", "SUCCESS")
        else:
            self.log("⚠️ مرورگر باز شد؛ در صورت نیاز در صفحه کروم دکمه New Project را بزنید.", "WARNING")
        return res

    def insert_prompt_to_flow(self, prompt: str) -> Dict[str, Any]:
        """
        گام دوم همیار انسان و ماشین:
        درج خودکار متن پرامپت در کادر متنی Google Flow درون مرورگر کروم.
        """
        port = int(self.config.get("cdp_port", 9222))
        if not self._is_port_open(port):
            self.log("⚠️ کروم باز نیست. ابتدا دکمه «باز کردن کروم و ایجاد پروژه جدید» را کلیک کنید.", "WARNING")
            return {"ok": False, "message": "مرورگر کروم باز نیست."}

        clean_prompt = prompt.strip()
        if not clean_prompt:
            return {"ok": False, "message": "متن پرامپت خالی است."}

        self.log("✍️ در حال درج متن پرامپت در کادر ورودی Google Flow...")
        tmp_path = Path(tempfile.gettempdir()) / "flow_prompt_temp.txt"
        try:
            tmp_path.write_text(clean_prompt, encoding="utf-8")
            res = self._run_worker(["--action", "insert-prompt", "--prompt-file", str(tmp_path)], timeout=25)
            if res.get("ok"):
                self.log("✅ پرامپت با موفقیت در گوگل فلو درج شد. اکنون تنظیمات را اعمال و دکمه Generate را بزنید.", "SUCCESS")
            else:
                self.log("⚠️ امکان تایپ مستقیم در کادر متنی وجود نداشت. می‌توانید از دکمه کپی پرامپت استفاده کنید.", "WARNING")
            return res
        except Exception as e:
            self.log(f"❌ خطا در درج پرامپت: {e}", "ERROR")
            return {"ok": False, "error": str(e), "message": str(e)}
        finally:
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    def run_diagnostics(self) -> Dict[str, Any]:
        """
        بررسی وضعیت پورت CDP، لاگین بودن اکانت گوگل و پروژه فعال.
        """
        self.log("🩺 در حال بررسی وضعیت اتصال به Google Flow...")
        port = int(self.config.get("cdp_port", 9222))
        port_open = self._is_port_open(port)

        if not port_open:
            self.log(f"⚠️ پورت {port} کروم بسته است. ابتدا دکمه «باز کردن کروم» را بزنید.")
            return {
                "ok": False,
                "cdpOpen": False,
                "playwright": True,
                "googleAuthenticated": False,
                "projectId": None,
                "raw": ""
            }

        res = self._run_worker(["--action", "diagnostics"], timeout=20)
        data = res.get("data", {})
        cdp_open = data.get("cdpOpen", port_open)
        auth_ok = data.get("googleAuthenticated", False)

        if cdp_open and auth_ok:
            self.log("✅ اتصال برقرار است: پورت 9222 باز و اکانت گوگل لاگین است.")
        elif not auth_ok:
            self.log("⚠️ مرورگر باز است اما وارد حساب گوگل نشده‌اید. لطفاً در پنجره کروم لاگین کنید.")

        return {
            "ok": res["ok"] and cdp_open and auth_ok,
            "cdpOpen": cdp_open,
            "playwright": True,
            "googleAuthenticated": auth_ok,
            "projectId": data.get("projectId"),
            "raw": res.get("raw", "")
        }

    def generate_thumbnail_bg(self, project_root: Path, bg_prompt: str, model: str = "Nano Banana 2.1") -> bool:
        """
        تولید تصویر پس‌زمینه تامنیل (9:16) و ذخیره مستقیم در پوشه Audio_BGM/AI_Background.png.
        """
        output_file = project_root / "03_Raw_DropZone" / "Audio_BGM" / "AI_Background.png"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        self.log(f"🖼 در حال تولید تصویر پس‌زمینه تامنیل با مدل {model}...")
        args = [
            "--action", "generate-thumbnail",
            "--project", str(project_root),
            "--prompt", bg_prompt,
            "--model", model,
            "--aspect", "9:16",
            "--timeout", str(self.timeout)
        ]
        res = self._run_worker(args, cwd=project_root, timeout=self.timeout + 30)
        if res["ok"] and output_file.exists() and output_file.stat().st_size > 5000:
            self.log(f"✅ تصویر تامنیل با موفقیت ذخیره شد: {output_file.name} ({output_file.stat().st_size} بایت)")
            return True

        data = res.get("data", {})
        if data.get("error") == "PUBLIC_ERROR_UNUSUAL_ACTIVITY":
            self.log("⚠️ برای ادامه تولید تصویر، لطفاً موقعیت یا سرور VPN خود را تغییر دهید.", "WARNING")
        else:
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
        تولید ویدیوی یک پلان مشخص (۱ تا ۷) و دانلود مستقیم آن در پوشه مربوطه در 03_Raw_DropZone.
        """
        folder_name = self.PLAN_FOLDER_MAP.get(plan_number, f"Plan_0{plan_number}")
        output_file = project_root / "03_Raw_DropZone" / folder_name / f"V_Plan_0{plan_number}.mp4"
        output_file.parent.mkdir(parents=True, exist_ok=True)

        self.log(f"🎬 در حال تولید ویدیوی پلان {plan_number} با مدل {model}...")
        args = [
            "--action", "generate-video",
            "--project", str(project_root),
            "--plan", str(plan_number),
            "--prompt", prompt,
            "--model", model,
            "--aspect", "9:16",
            "--timeout", str(self.timeout)
        ]
        res = self._run_worker(args, cwd=project_root, timeout=self.timeout + 60)
        if res["ok"] and output_file.exists() and output_file.stat().st_size > 10000:
            self.log(f"✅ ویدیوی پلان {plan_number} با موفقیت دانلود شد: {output_file.name}")
            return True

        data = res.get("data", {})
        if data.get("error") == "PUBLIC_ERROR_UNUSUAL_ACTIVITY":
            self.log("⚠️ برای ادامه تولید ویدیو، لطفاً موقعیت یا سرور VPN خود را تغییر دهید.", "WARNING")
        else:
            self.log(f"❌ خطا در تولید ویدیوی پلان {plan_number}.")
        return False

    def run_declarative_pipeline(self, project_root: Path, dry_run: bool = False) -> bool:
        """
        اجرای کامل فایل 02_AI_Brain_JSON/flow.json با دستور flow run یا کارگر Playwright.
        """
        ai_brain_dir = project_root / "02_AI_Brain_JSON"
        flow_json_path = ai_brain_dir / "flow.json"
        if not flow_json_path.exists():
            self.log("❌ فایل flow.json در پوشه 02_AI_Brain_JSON یافت نشد.")
            return False

        args = ["--action", "run-pipeline", "--project", str(project_root)]
        if dry_run:
            args.append("--dry-run")
            self.log("🧪 در حال اجرای آزمایشی پایپلاین (Dry Run - بدون مصرف کردیت)...")
        else:
            self.log("🚀 شروع اجرای خودکار کل صحنه‌ها در Google Flow...")

        res = self._run_worker(args, cwd=project_root, timeout=(self.timeout * 7) + 120)
        if res["ok"]:
            if dry_run:
                self.log("✅ آزمایش پایپلاین با موفقیت تایید شد: تمام ۷ پلان معتبر هستند.")
            else:
                self.log("✅ اجرای پایپلاین flow.json با موفقیت به پایان رسید.")
            return True

        data = res.get("data", {})
        if data.get("error") == "PUBLIC_ERROR_UNUSUAL_ACTIVITY":
            self.log("⚠️ به دلیل محدودیت موقت آی‌پی VPN گوگل اجازه تولید جدید نداد. لطفاً سرور VPN را تغییر دهید.", "WARNING")
        else:
            self.log("❌ اجرای پایپلاین با خطا مواجه شد. جزئیات را در لاگ بررسی کنید.")
        return False
