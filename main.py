import math
import traceback
from datetime import datetime
import pytz
import uuid
import json
import random
import re
import time
import os
import requests
from util.aes_help import encrypt_data, decrypt_data
import util.zepp_helper as zeppHelper

# 获取默认值转int:
def get_int_value_default(_config: dict, _key, default):
    _config.setdefault(_key, default)
    try:
        val = _config.get(_key)
        if val is None:
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


# 获取当前时间对应的最大和最小步数
def get_min_max_by_time(hour=None, minute=None):
    if hour is None:
        hour = time_bj.hour
    if minute is None:
        minute = time_bj.minute
    time_rate = min((hour * 60 + minute) / (22 * 60), 1)
    min_step_conf = get_int_value_default(config, 'MIN_STEP', 18000)
    max_step_conf = get_int_value_default(config, 'MAX_STEP', 25000)
    # 按时间比率计算区间
    calc_min = int(time_rate * min_step_conf)
    calc_max = int(time_rate * max_step_conf)
    # 如果 time_rate>0 且 calc_min 为 0，则至少设为 1，避免在非零时间段产生 0 步
    if time_rate > 0 and calc_min == 0:
        calc_min = 1
    # 确保最大值不小于最小值
    if calc_max < calc_min:
        calc_max = calc_min
    return calc_min, calc_max


# 虚拟ip地址
def fake_ip():
    return f"{223}.{random.randint(64, 117)}.{random.randint(0, 255)}.{random.randint(0, 255)}"


# 账号脱敏
def desensitize_user_name(user):
    if user is None:
        return ""
    if len(user) <= 8:
        ln = max(math.floor(len(user) / 3), 1)
        return f'{user[:ln]}***{user[-ln:]}'
    return f'{user[:3]}****{user[-4:]}'


# 获取北京时间
def get_beijing_time():
    target_timezone = pytz.timezone('Asia/Shanghai')
    return datetime.now().astimezone(target_timezone)


# 格式化时间
def format_now():
    return get_beijing_time().strftime("%Y-%m-%d %H:%M:%S")


# 获取时间戳
def get_time():
    current_time = get_beijing_time()
    return "%.0f" % (current_time.timestamp() * 1000)


# 获取登录code
def get_access_token(location):
    code_pattern = re.compile("(?<=access=).*?(?=&)")
    result = code_pattern.findall(location)
    if result is None or len(result) == 0:
        return None
    return result[0]


def get_error_code(location):
    code_pattern = re.compile("(?<=error=).*?(?=&)")
    result = code_pattern.findall(location)
    if result is None or len(result) == 0:
        return None
    return result[0]


# PushPlus 消息推送
def push_plus(title, content):
    requestUrl = f"http://www.pushplus.plus/send"
    data = {
        "token": PUSH_PLUS_TOKEN,
        "title": title,
        "content": content,
        "template": "html",
        "channel": "wechat"
    }
    try:
        response = requests.post(requestUrl, data=data, timeout=10)
        if response.status_code == 200:
            json_res = response.json()
            print(f"pushplus推送完毕：{json_res['code']}-{json_res['msg']}")
        else:
            print(f"pushplus推送失败，状态码：{response.status_code}")
    except Exception as e:
        print(f"pushplus推送异常: {e}")


def escape_html(text: str) -> str:
    if text is None:
        return ""
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&#39;")
    return text


def push_to_telegram(title: str, content_lines: list):
    global TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        print("Telegram 配置不完整，跳过推送")
        return
    now = format_now()
    
    html_messages = []
    html_messages.append(f"<b>{escape_html(title)}</b>\n")
    html_messages.append(f"<b>时间</b>: {escape_html(now)}\n")
    html_messages.extend(content_lines)  
    html_text = "\n".join(html_messages)
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": html_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    
    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("Telegram 推送完毕")
        else:
            print(f"Telegram 推送失败: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"Telegram 推送异常: {e}")


class MiMotionRunner:
    def __init__(self, _user, _passwd):
        self.user_id = None
        self.device_id = str(uuid.uuid4())
        user = str(_user)
        password = str(_passwd)
        self.invalid = False
        self.log_str = ""
        if user == '' or password == '':
            self.error = "用户名或密码填写有误！"
            self.invalid = True
            pass
        self.password = password
        if (user.startswith("+86")) or "@" in user:
            user = user
        else:
            user = "+86" + user
        if user.startswith("+86"):
            self.is_phone = True
        else:
            self.is_phone = False
        self.user = user
        self.fake_ip_addr = fake_ip()
        self.log_str += f"创建虚拟ip地址：{self.fake_ip_addr}\n"

    # 登录
    def login(self):
        user_token_info = user_tokens.get(self.user)
        if user_token_info is not None:
            access_token = user_token_info.get("access_token")
            login_token = user_token_info.get("login_token")
            app_token = user_token_info.get("app_token")
            self.device_id = user_token_info.get("device_id")
            self.user_id = user_token_info.get("user_id")
            if self.device_id is None:
                self.device_id = str(uuid.uuid4())
                user_token_info["device_id"] = self.device_id
            ok, msg = zeppHelper.check_app_token(app_token)
            if ok:
                self.log_str += "使用加密保存的app_token\n"
                return app_token
            else:
                self.log_str += f"app_token失效，重新获取 last grant time: {user_token_info.get('app_token_time')}\n"
                # 检查login_token是否可用
                app_token, msg = zeppHelper.grant_app_token(login_token)
                if app_token is None:
                    self.log_str += f"login_token 失效，重新获取 last grant time: {user_token_info.get('login_token_time')}\n"
                    login_token, app_token, user_id, msg = zeppHelper.grant_login_tokens(access_token, self.device_id, self.is_phone)
                    if login_token is None:
                        self.log_str += f"登录提取的 access_token 无效：{msg}"
                        return None
                    else:
                        user_token_info["login_token"] = login_token
                        user_token_info["app_token"] = app_token
                        user_token_info["user_id"] = user_id
                        user_token_info["login_token_time"] = get_time()
                        user_token_info["app_token_time"] = get_time()
                        self.user_id = user_id
                        return app_token

        access_token, msg = zeppHelper.login_access_token(self.user, self.password)
        if access_token is None:
            self.log_str += "登录获取accessToken失败：%s" % msg
            return None

        login_token, app_token, user_id, msg = zeppHelper.grant_login_tokens(access_token, self.device_id, self.is_phone)
        if login_token is None:
            self.log_str += f"登录提取的 access_token 无效：{msg}"
            return None

        user_token_info = dict()
        user_token_info["access_token"] = access_token
        user_token_info["login_token"] = login_token
        user_token_info["app_token"] = app_token
        user_token_info["user_id"] = user_id
        user_token_info["access_token_time"] = get_time()
        user_token_info["login_token_time"] = get_time()
        user_token_info["app_token_time"] = get_time()
        if self.device_id is None:
            self.device_id = uuid.uuid4()
        user_token_info["device_id"] = self.device_id
        user_tokens[self.user] = user_token_info
        return app_token


    # 主函数
    def login_and_post_step(self, min_step, max_step):
        if self.invalid:
            return "账号或密码配置有误", False
        app_token = self.login()
        if app_token is None:
            return "登录失败！", False       
        
        last = 0
        try:
            last = int(user_tokens.get(self.user, {}).get("last_step", 0) or 0)
        except (ValueError, TypeError):
            last = 0
        
        effective_lower = last
        if effective_lower == 0:
            initial_submit_min_step = get_int_value_default(config, 'INITIAL_SUBMIT_MIN_STEP', 100)
            if initial_submit_min_step <= 0:
                initial_submit_min_step = 100 
            effective_lower = initial_submit_min_step
            self.log_str += f"注意：发现 last_step 为 0，已将首次提交的最低步数提升到 {effective_lower} (可配置 INITIAL_SUBMIT_MIN_STEP)。\n"
        
        lower = max(int(min_step), effective_lower)
        
        if lower > int(max_step):
            step_val = lower
        else:
            step_val = random.randint(int(lower), int(max_step))
        
        self.log_str += f"已设置为随机步数范围({min_step}~{max_step})，下限取 max(min_step_config,{desensitize_user_name(self.user)}_last_step)={last}，修正后实际计算下限：{lower}，最终步数:{step_val}\n"      
        
        ok, msg = zeppHelper.post_fake_brand_data(str(step_val), app_token, self.user_id)
        
        try:
            user_token_info = user_tokens.setdefault(self.user, {})
            user_token_info["last_step"] = int(step_val)
        except Exception as e:
            self.log_str += f"更新 last_step 失败: {e}\n"
        
        return f"修改步数（{step_val}）[" + msg + "]", ok


# 单账号执行逻辑
def run_single_account(total, idx, user_mi, passwd_mi):
    idx_info = ""
    if idx is not None:
        idx_info = f"[{idx + 1}/{total}]"
    log_str = f"[{format_now()}]\n{idx_info}账号：{desensitize_user_name(user_mi)}\n"
    try:
        runner = MiMotionRunner(user_mi, passwd_mi)
        exec_msg, success = runner.login_and_post_step(min_step, max_step)
        log_str += runner.log_str
        log_str += f'{exec_msg}\n'
        exec_result = {"user": user_mi, "success": success,
                       "msg": exec_msg}
    except Exception as e:
        log_str += f"执行异常:{traceback.format_exc()}\n"
        exec_result = {"user": user_mi, "success": False,
                       "msg": f"执行异常:{traceback.format_exc()}"}
    print(log_str)
    return exec_result


# 推送 PushPlus
def push_to_push_plus(exec_results, summary):
    global PUSH_PLUS_TOKEN, PUSH_PLUS_MAX
    if not (PUSH_PLUS_TOKEN and PUSH_PLUS_TOKEN != '' and PUSH_PLUS_TOKEN != 'NO'):
        print("PushPlus 配置不完整，跳过推送")
        return
    
    html = f'<div>{summary}</div>'
    if len(exec_results) >= PUSH_PLUS_MAX:
        html += '<div>账号数量过多，详细情况请前往github actions中查看</div>'
    else:
        html += '<ul>'
        for exec_result in exec_results:
            success = exec_result['success']
            if success:
                html += f'<li><span>账号：{escape_html(exec_result["user"])}</span>刷步数成功，接口返回：{escape_html(exec_result["msg"])}</li>'
            else:
                html += f'<li><span>账号：{escape_html(exec_result["user"])}</span>刷步数失败，失败原因：{escape_html(exec_result["msg"])}</li>'
        html += '</ul>'
    push_plus(f"{format_now()} 刷步数通知", html)


def prepare_user_tokens() -> dict:
    data_path = r"encrypted_tokens.data"
    if os.path.exists(data_path):
        with open(data_path, 'rb') as f:
            data = f.read()
        try:
            decrypted_data = decrypt_data(data, aes_key, None)
            return json.loads(decrypted_data.decode('utf-8', errors='strict'))
        except Exception as e:
            print(f"密钥不正确或者加密内容损坏，放弃已保存的 token 文件: {e}")
            return dict()
    else:
        return dict()


def persist_user_tokens():
    data_path = r"encrypted_tokens.data"
    origin_str = json.dumps(user_tokens, ensure_ascii=False)
    cipher_data = encrypt_data(origin_str.encode("utf-8"), aes_key, None)
    with open(data_path, 'wb') as f:
        f.write(cipher_data)
        f.flush()
        f.close()


def reset_daily_steps(user_tokens: dict, log_reset_hour: int = 6, log_reset_window_end_hour: int = 8):
    try:
        global time_bj, encrypt_support
        changed = False
        current_date_str = time_bj.strftime("%Y-%m-%d")
        is_in_log_window = log_reset_hour <= time_bj.hour < log_reset_window_end_hour 

        for user, info in list(user_tokens.items()):
            last_reset_date = info.get("last_reset_date")
            
            if last_reset_date != current_date_str:
                needs_reset = False
                try:
                    if info.get("last_step") is not None and int(info.get("last_step")) != 0:
                        needs_reset = True
                except (ValueError, TypeError):
                    needs_reset = True
                
                if needs_reset or last_reset_date is None:
                    info["last_step"] = 0 
                    info["last_reset_date"] = current_date_str
                    changed = True

        if changed:
            if is_in_log_window:
                print(f"[{time_bj.strftime('%H:%M')}] 已在北京时间 {log_reset_hour} 点至 {log_reset_window_end_hour-1} 点范围内，对部分/所有账号进行日重置（last_step设为0，并更新重置日期）。")
            else:
                print(f"[{time_bj.strftime('%H:%M')}] 已对部分/所有账号在当日首次运行中进行日重置（last_step设为0，并更新重置日期）。")

            if encrypt_support:
                try:
                    persist_user_tokens()
                    print("重置后已持久化加密 token 数据")
                except Exception as e:
                    print(f"持久化 token 失败: {e}")
        else:
            if is_in_log_window:
                print(f"[{time_bj.strftime('%H:%M')}] 重置检查：所有账号 last_step 已为 0 且今日已重置，或当前已在重置窗口内但无需操作。")
            else:
                 print(f"[{time_bj.strftime('%H:%M')}] 重置检查：今日已重置过，无需再次操作（当前不在重置窗口）。")

    except Exception as e:
        print(f"执行 reset_daily_steps 异常: {e}")


if __name__ == "__main__":
    # 北京时间
    time_bj = get_beijing_time()
    encrypt_support = False
    user_tokens = dict()
    aes_key = None

    # AES Key处理
    if os.environ.__contains__("AES_KEY") and os.environ.get("AES_KEY"):
        aes_key = os.environ.get("AES_KEY").encode('utf-8')
        if len(aes_key) == 16:
            encrypt_support = True
            user_tokens = prepare_user_tokens()
        else:
            print("AES_KEY长度不为16字节，无法使用加密保存功能")
    else:
        print("AES_KEY未设置，无法使用加密保存功能")

    # CONFIG处理
    if os.environ.__contains__("CONFIG") is False:
        print("未配置CONFIG变量，无法执行")
        exit(1)
    else:
        # region 初始化参数
        config = dict()
        try:
            config = json.loads(os.environ.get("CONFIG")) # Removed unnecessary dict() conversion
        except Exception as e:
            print(f"CONFIG格式不正确，请检查Secret配置，请严格按照JSON格式：使用双引号包裹字段和值，逗号不能多也不能少。错误: {e}")
            traceback.print_exc()
            exit(1)
        
        # 配置变量
        TELEGRAM_TOKEN = config.get('TELEGRAM_TOKEN')
        TELEGRAM_CHAT_ID = config.get('TELEGRAM_CHAT_ID')

        PUSH_PLUS_TOKEN = config.get('PUSH_PLUS_TOKEN')
        PUSH_PLUS_MAX = get_int_value_default(config, 'PUSH_PLUS_MAX', 30)
        
        sleep_seconds = config.get('SLEEP_GAP')
        if sleep_seconds is None or str(sleep_seconds).strip() == '':
            sleep_seconds = 5
        try:
            sleep_seconds = float(sleep_seconds)
        except ValueError:
            print(f"SLEEP_GAP配置'{sleep_seconds}'无效，使用默认值5秒。")
            sleep_seconds = 5.0

        users = config.get('USER')
        passwords = config.get('PWD')
        if users is None or passwords is None:
            print("未正确配置账号密码，无法执行")
            exit(1)

        PUSH_REPORT_HOUR = get_int_value_default(config, 'PUSH_REPORT_HOUR', -1)

        min_step, max_step = get_min_max_by_time()
        
        use_concurrent = config.get('USE_CONCURRENT')
        if use_concurrent is not None and str(use_concurrent).lower() == 'true':
            use_concurrent = True
        else:
            print(f"多账号执行间隔：{sleep_seconds}秒")
            use_concurrent = False

        reset_daily_steps(user_tokens)

        # endregion

        # 执行主流程
        exec_results = []
        user_list = users.split('#')
        password_list = passwords.split('#')
        total = len(user_list)

        if total == len(password_list):
            if use_concurrent:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=min(total, os.cpu_count() or 1)) as executor:
                    exec_results = list(executor.map(lambda x: run_single_account(total, x[0], x[1][0], x[1][1]), enumerate(zip(user_list, password_list))))
            else:
                for idx, (user_mi, passwd_mi) in enumerate(zip(user_list, password_list)):
                    exec_results.append(run_single_account(total, idx, user_mi, passwd_mi))
                    if idx < total - 1:
                        time.sleep(sleep_seconds)
        else:
            print(f"账号数长度[{total}]和密码数长度[{len(password_list)}]不匹配，跳过执行")
            exit(1)

        if encrypt_support:
            try:
                persist_user_tokens()
            except Exception as e:
                print(f"持久化token失败：{e}")


        success_count = 0
        push_results = []
        for result in exec_results:
            push_results.append(result)
            if result['success'] is True:
                success_count += 1

        current_hour_bj = time_bj.hour 
        should_push = (PUSH_REPORT_HOUR == -1) or (current_hour_bj == PUSH_REPORT_HOUR)

        if should_push:
            summary_msg = f"\n执行账号总数{total}，成功：{success_count}，失败：{total - success_count}"
            
            # 推送 PushPlus
            push_to_push_plus(push_results, summary_msg)

            # 推送 Telegram
            if TELEGRAM_TOKEN and TELEGRAM_CHAT_ID:
                telegram_lines_to_send = []
                
                telegram_lines_to_send.append(f"<b>{escape_html('步数增加-执行摘要')}</b>\n")
                telegram_lines_to_send.append(f"<b>总计</b>: {escape_html(str(total))} | <b>成功</b>: {escape_html(str(success_count))} | <b>失败</b>: {escape_html(str(total - success_count))}\n")
                
                if len(exec_results) >= PUSH_PLUS_MAX:
                    telegram_lines_to_send.append(escape_html("账号数量过多，详细情况请前往 GitHub Actions 中查看\n"))
                else:
                    telegram_lines_to_send.append(f"<b>{escape_html('详细结果')}</b>\n")
                    for result in exec_results:
                        user_esc = escape_html(desensitize_user_name(result['user']))
                        reason_esc = escape_html(result['msg']) 
                        status_emoji = "✅" if result['success'] else "❌"
                        telegram_lines_to_send.append(
                            f"{status_emoji} <b>账号</b>: {user_esc} -> {reason_esc}\n"
                        )
                push_to_telegram("步数通知", telegram_lines_to_send)
        else:
            print(f"当前北京时间 {time_bj.strftime('%H:%M')}，不满足配置的推送小时 PUSH_REPORT_HOUR={PUSH_REPORT_HOUR} 的要求，跳过消息推送。")
