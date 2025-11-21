# -*- coding: utf8 -*-
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

# 获取默认值转int
def get_int_value_default(_config: dict, _key, default):
    _config.setdefault(_key, default)
    return int(_config.get(_key))


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
        response = requests.post(requestUrl, data=data)
        if response.status_code == 200:
            json_res = response.json()
            print(f"pushplus推送完毕：{json_res['code']}-{json_res['msg']}")
        else:
            print(f"pushplus推送失败，状态码：{response.status_code}")
    except:
        print("pushplus推送异常")


# 针对 HTML parse_mode 的转义函数
def escape_html(text: str) -> str:
    if text is None:
        return ""
    # 对 HTML 特殊字符进行转义
    # 仅需转义 < > & " '
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    text = text.replace('"', "&quot;")
    text = text.replace("'", "&#39;") # 或 &apos; 但部分旧浏览器可能不支持，&#39;更通用
    return text


def push_to_telegram(title: str, content_lines: list):
    global TELEGRAM_TOKEN, TELEGRAM_CHAT_ID
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        print("Telegram 配置不完整，跳过推送")
        return
    now = format_now()
    
    # 构造 HTML 消息
    # 头部信息，包括标题和时间
    html_messages = []
    html_messages.append(f"<b>{escape_html(title)}</b>\n") # 标题加粗
    html_messages.append(f"<b>时间</b>: {escape_html(now)}\n") # 时间加粗
    
    # 添加具体内容行，这些行在调用前已经被适当转义并处理成 HTML 格式
    # 由于是列表，可以使用 <pre> 或直接换行
    html_messages.extend(content_lines)
    
    html_text = "\n".join(html_messages) # 将所有行连接成一个大字符串
    
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": html_text,
        "parse_mode": "HTML", # <--- 这里改为 HTML
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
        # self.fake_ip_addr = fake_ip()
        # self.log_str += f"创建虚拟ip地址：{self.fake_ip_addr}\n"

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

        # access_token 失效 或者没有保存加密数据
        access_token, msg = zeppHelper.login_access_token(self.user, self.password)
        if access_token is None:
            self.log_str += "登录获取accessToken失败：%s" % msg
            return None

        # print(f"device_id:{self.device_id} isPhone: {self.is_phone}")
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
        except:
            last = 0
        lower = max(int(min_step), last)
        if lower > int(max_step):
            step_val = lower
        else:
            step_val = random.randint(int(lower), int(max_step))
        self.log_str += f"已设置为随机步数范围({min_step}~{max_step})，下限取 max(min_step,last_step)={lower}，最终步数:{step_val}\n"
        ok, msg = zeppHelper.post_fake_brand_data(str(step_val), app_token, self.user_id)
        try:
            user_token_info = user_tokens.setdefault(self.user, {})
            user_token_info["last_step"] = int(step_val)
        except:
            pass
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
    except:
        log_str += f"执行异常:{traceback.format_exc()}\n"
        log_str += traceback.format_exc()
        exec_result = {"user": user_mi, "success": False,
                       "msg": f"执行异常:{traceback.format_exc()}"}
    print(log_str)
    return exec_result


# 推送 PushPlus（保留）
def push_to_push_plus(exec_results, summary):
    # 判断是否需要pushplus推送
    if PUSH_PLUS_TOKEN is not None and PUSH_PLUS_TOKEN != '' and PUSH_PLUS_TOKEN != 'NO':
        if PUSH_PLUS_HOUR is not None and PUSH_PLUS_HOUR.isdigit():
            if time_bj.hour != int(PUSH_PLUS_HOUR):
                print(f"当前设置push_plus推送整点为：{PUSH_PLUS_HOUR}, 当前整点为：{time_bj.hour}，跳过推送")
                return
        html = f'<div>{summary}</div>'
        if len(exec_results) >= PUSH_PLUS_MAX:
            html += '<div>账号数量过多，详细情况请前往github actions中查看</div>'
        else:
            html += '<ul>'
            for exec_result in exec_results:
                success = exec_result['success']
                if success is not None and success is True:
                    html += f'<li><span>账号：{exec_result["user"]}</span>刷步数成功，接口返回：{exec_result["msg"]}</li>'
                else:
                    html += f'<li><span>账号：{exec_result["user"]}</span>刷步数失败，失败原因：{exec_result["msg"]}</li>'
            html += '</ul>'
        push_plus(f"{format_now()} 刷步数通知", html)


def prepare_user_tokens() -> dict:
    data_path = r"encrypted_tokens.data"
    if os.path.exists(data_path):
        with open(data_path, 'rb') as f:
            data = f.read()
        try:
            decrypted_data = decrypt_data(data, aes_key, None)
            # 假设原始明文为 UTF-8 编码文本
            return json.loads(decrypted_data.decode('utf-8', errors='strict'))
        except:
            print("密钥不正确或者加密内容损坏 放弃token")
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


if __name__ == "__main__":
    # 北京时间
    time_bj = get_beijing_time()
    encrypt_support = False
    user_tokens = dict()
    if os.environ.__contains__("AES_KEY") is True:
        aes_key = os.environ.get("AES_KEY")
        if aes_key is not None:
            aes_key = aes_key.encode('utf-8')
            if len(aes_key) == 16:
                encrypt_support = True
        if encrypt_support:
            user_tokens = prepare_user_tokens()
        else:
            print("AES_KEY未设置或无效，无法使用加密保存功能")
    if os.environ.__contains__("CONFIG") is False:
        print("未配置CONFIG变量，无法执行")
        exit(1)
    else:
        # region 初始化参数
        config = dict()
        try:
            config = dict(json.loads(os.environ.get("CONFIG")))
        except:
            print("CONFIG格式不正确，请检查Secret配置，请严格按照JSON格式：使用双引号包裹字段和值，逗号不能多也不能少")
            traceback.print_exc()
            exit(1)

        # 配置变量
        PUSH_PLUS_TOKEN = config.get('PUSH_PLUS_TOKEN')
        PUSH_PLUS_HOUR = config.get('PUSH_PLUS_HOUR')
        PUSH_PLUS_MAX = get_int_value_default(config, 'PUSH_PLUS_MAX', 30)
        sleep_seconds = config.get('SLEEP_GAP')
        if sleep_seconds is None or sleep_seconds == '':
            sleep_seconds = 5
        sleep_seconds = float(sleep_seconds)
        users = config.get('USER')
        passwords = config.get('PWD')
        if users is None or passwords is None:
            print("未正确配置账号密码，无法执行")
            exit(1)

        min_step, max_step = get_min_max_by_time()
        use_concurrent = config.get('USE_CONCURRENT')
        if use_concurrent is not None and use_concurrent == 'True':
            use_concurrent = True
        else:
            print(f"多账号执行间隔：{sleep_seconds}")
            use_concurrent = False

        # 从配置中读取 Telegram 相关参数
        TELEGRAM_TOKEN = config.get('TELEGRAM_TOKEN')
        TELEGRAM_CHAT_ID = config.get('TELEGRAM_CHAT_ID')

        # endregion

        # 执行主流程
        exec_results = []
        if len(users.split('#')) == len(passwords.split('#')):
            idx, total = 0, len(users.split('#'))
            if use_concurrent:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    exec_results = list(executor.map(lambda x: run_single_account(total, x[0], *x[1]), enumerate(zip(users.split('#'), passwords.split('#')))))
            else:
                for user_mi, passwd_mi in zip(users.split('#'), passwords.split('#')):
                    exec_results.append(run_single_account(total, idx, user_mi, passwd_mi))
                    idx += 1
                    if idx < total:
                        time.sleep(sleep_seconds)
        else:
            print(f"账号数长度[{len(users.split('#'))}]和密码数长度[{len(passwords.split('#'))}]不匹配，跳过执行")
            exit(1)

        if encrypt_support:
            persist_user_tokens()

        success_count = 0
        push_results = []
        for result in exec_results:
            push_results.append(result)
            if result['success'] is True:
                success_count += 1

        summary = f"\n执行账号总数{total}，成功：{success_count}，失败：{total - success_count}"

        # 推送 PushPlus 及 Telegram
        push_to_push_plus(push_results, summary)
        if TELEGRAM_TOKEN is not None and TELEGRAM_CHAT_ID is not None:
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
