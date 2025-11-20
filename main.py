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
from util.aes_help import  encrypt_data, decrypt_data
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
    min_step = get_int_value_default(config, 'MIN_STEP', 18000)
    max_step = get_int_value_default(config, 'MAX_STEP', 25000)
    return int(time_rate * min_step), int(time_rate * max_step)


# 虚拟ip地址
def fake_ip():
    # 随便找的国内IP段：223.64.0.0 - 223.117.255.255
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
    # 获取当前时间
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


# pushplus消息推送
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
            print("pushplus推送失败")
    except:
        print("pushplus推送异常")

# 新增：Telegram 推送函数
def push_telegram(title, content):
    """
    使用 Telegram Bot API 发送消息。CONFIG 中可配置：
      TELEGRAM_TOKEN, TELEGRAM_CHAT_ID, 可选 TELEGRAM_HOUR, TELEGRAM_MAX
    """
    if TELEGRAM_TOKEN is None or TELEGRAM_TOKEN == '' or TELEGRAM_CHAT_ID is None or TELEGRAM_CHAT_ID == '':
        return
    # 小时限制（如设置则仅在整点发送）
    if TELEGRAM_HOUR is not None and str(TELEGRAM_HOUR).isdigit():
        if time_bj.hour != int(TELEGRAM_HOUR):
            print(f"当前设置telegram推送整点为：{TELEGRAM_HOUR}, 当前整点为：{time_bj.hour}，跳过推送")
            return
    # 限制长度并使用 HTML 格式
    full_text = f"<b>{title}</b>\n{content}"
    max_len = 3500
    if len(full_text) > max_len:
        full_text = full_text[:max_len-6] + "...(truncated)"
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": full_text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }
    try:
        resp = requests.post(url, data=payload, timeout=10)
        if resp.status_code == 200:
            print("telegram 推送完毕")
        else:
            print(f"telegram 推送失败: {resp.status_code} {resp.text}")
    except Exception as e:
        print(f"telegram 推送异常: {e}")

# 修改：push_to_push_plus 改为分别处理 pushplus 与 telegram（互不影响）
def push_to_push_plus(exec_results, summary):
    # pushplus 部分
    if PUSH_PLUS_TOKEN is not None and PUSH_PLUS_TOKEN != '' and PUSH_PLUS_TOKEN != 'NO':
        if PUSH_PLUS_HOUR is not None and str(PUSH_PLUS_HOUR).isdigit():
            if time_bj.hour != int(PUSH_PLUS_HOUR):
                print(f"当前设置push_plus推送整点为：{PUSH_PLUS_HOUR}, 当前整点为：{time_bj.hour}，跳过 pushplus 推送")
            else:
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
        else:
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

    # telegram 部分（如果配置了则推送）
    if 'TELEGRAM_TOKEN' in globals() or 'TELEGRAM_CHAT_ID' in globals():
        # TELEGRAM_TOKEN/TELEGRAM_CHAT_ID 在 __main__ CONFIG 解析时会被赋值，如果未配置则为 None
        pass
    if TELEGRAM_TOKEN is not None and TELEGRAM_TOKEN != '' and TELEGRAM_CHAT_ID is not None and TELEGRAM_CHAT_ID != '':
        text = summary + "\n"
        if len(exec_results) <= TELEGRAM_MAX:
            for exec_result in exec_results:
                if exec_result.get('success'):
                    text += f"账号：{desensitize_user_name(exec_result['user'])} 成功\n"
                else:
                    text += f"账号：{desensitize_user_name(exec_result['user'])} 失败：{exec_result['msg']}\n"
        else:
            text += "账号数量过多，详细情况请前往 GitHub Actions 查看。\n"
        push_telegram(f"{format_now()} 刷步数通知", text)

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


def execute():
    user_list = users.split('#')
    passwd_list = passwords.split('#')
    exec_results = []
    if len(user_list) == len(passwd_list):
        idx, total = 0, len(user_list)
        if use_concurrent:
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                exec_results = executor.map(lambda x: run_single_account(total, x[0], *x[1]),
                                            enumerate(zip(user_list, passwd_list)))
        else:
            for user_mi, passwd_mi in zip(user_list, passwd_list):
                exec_results.append(run_single_account(total, idx, user_mi, passwd_mi))
                idx += 1
                if idx < total:
                    # 每个账号之间间隔一定时间请求一次，避免接口请求过于频繁导致异常
                    time.sleep(sleep_seconds)
        if encrypt_support:
            persist_user_tokens()
        success_count = 0
        push_results = []
        for result in exec_results:
            push_results.append(result)
            if result['success'] is True:
                success_count += 1
        summary = f"\n执行账号总数{total}，成功：{success_count}，失败：{total - success_count}"
        print(summary)
        push_to_push_plus(push_results, summary)
    else:
        print(f"账号数长度[{len(user_list)}]和密码数长度[{len(passwd_list)}]不匹配，跳过执行")
        exit(1)


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
            print("AES_KEY未设置或者无效 无法使用加密保存功能")
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
        PUSH_PLUS_TOKEN = config.get('PUSH_PLUS_TOKEN')
        PUSH_PLUS_HOUR = config.get('PUSH_PLUS_HOUR')
        PUSH_PLUS_MAX = get_int_value_default(config, 'PUSH_PLUS_MAX', 30)

        # 新增：Telegram 配置项（可选）
        TELEGRAM_TOKEN = config.get('TELEGRAM_TOKEN')            # Bot Token，例如：123456:ABC-DEF...
        TELEGRAM_CHAT_ID = config.get('TELEGRAM_CHAT_ID')        # chat_id 或 @channelusername
        TELEGRAM_HOUR = config.get('TELEGRAM_HOUR')              # 可选，整点推送限制
        TELEGRAM_MAX = get_int_value_default(config, 'TELEGRAM_MAX', 30)

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
        # endregion
        execute()
