# -*- coding: utf-8 -*-
"""批量上传本地官方预设到 GitHub 仓库。

用法：
  1. 第一次运行先设置 Token：
     python tools/upload_presets.py --token ghp_xxxxxxxxxxxx

  2. 之后直接跑：
     python tools/upload_presets.py

Token 获取：https://github.com/settings/tokens → Generate new token (classic)
  勾选 repo 权限即可。
"""

import json
import os
import sys
import base64
import urllib.request
import urllib.error
from urllib.parse import quote

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRESETS_DIR = os.path.join(ROOT, "presets", "official")
TOKEN_FILE = os.path.join(ROOT, "tools", ".github_token")

OWNER = "JadeYingWah"
REPO = "WutheringWavesDmgCalc"
BRANCH = "main"
CATEGORY_DIRS = ["character", "weapon", "echo_set", "character_buff"]

API_BASE = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/presets/official"


def get_token():
    """读取保存的 Token。"""
    if os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE, "r") as f:
            return f.read().strip()
    return None


def save_token(token):
    os.makedirs(os.path.dirname(TOKEN_FILE), exist_ok=True)
    with open(TOKEN_FILE, "w") as f:
        f.write(token)


def github_api(method, url, data=None):
    """调用 GitHub API。"""
    token = get_token()
    if not token:
        print("[错误] 未设置 GitHub Token")
        print(f"请运行: python tools/upload_presets.py --token ghp_xxxx")
        sys.exit(1)

    body = json.dumps(data).encode("utf-8") if data else None
    req = urllib.request.Request(url, data=body, method=method)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    req.add_header("User-Agent", "WWDmgCalc-PresetUploader/1.0")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            content = resp.read().decode("utf-8")
            if content:
                return json.loads(content)
            return None
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        detail = ""
        if e.code == 403:
            if "token" in err_body.lower():
                detail = "（Token 权限不足，请检查 Contents: Read and write）"
            elif "rate limit" in err_body.lower():
                detail = "（API 限流，等几分钟再试）"
            else:
                detail = "（无权限访问该资源）"
        elif e.code == 404:
            detail = "（路径不存在，可能是仓库名或目录名错了）"
        elif e.code == 422:
            detail = "（请求格式错误，可能是路径或编码问题）"
        elif e.code == 409:
            detail = "（文件冲突，GitHub 上已被其他人修改）"
        print(f"  HTTP {e.code}: {err_body[:100]}")
        if detail:
            print(f"  {detail}")
        return None


def upload_file(category, filename, content):
    """上传单个文件到 GitHub。返回 True/False。"""
    path = f"presets/official/{category}/{filename}"
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{quote(path, safe="/")}"

    # 检查文件是否已存在（获取 sha 用于更新）
    existing = github_api("GET", url)
    data = {
        "message": f"更新预设: {category}/{filename}",
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": BRANCH,
    }
    if existing and "sha" in existing:
        data["sha"] = existing["sha"]
        data["message"] = f"更新预设: {category}/{filename}"
    else:
        data["message"] = f"新增预设: {category}/{filename}"

    result = github_api("PUT", url, data)
    if result is None:
        # 给出更具体的错误提示
        import sys
        print("\n  ❌ 上传失败，常见原因：")
        print("    1. Token 权限不足 → 检查 Contents: Read and write")
        print("    2. 仓库选择不对 → 检查 Token 绑定了哪个仓库")
        print("    3. 网络连接问题 → 检查 VPN 是否断开")
        print("    4. 文件名含非法字符 → 检查文件名\n")
        return False
    return True


def build_manifest():
    """扫描本地 presets/official/ 生成 manifest.json。"""
    manifest = {}
    for cat in CATEGORY_DIRS:
        cat_dir = os.path.join(PRESETS_DIR, cat)
        if os.path.isdir(cat_dir):
            manifest[cat] = sorted(
                f for f in os.listdir(cat_dir) if f.endswith(".json")
            )
        else:
            manifest[cat] = []
    return manifest


def main():
    # ── 处理命令行参数 ──
    if len(sys.argv) >= 3 and sys.argv[1] == "--token":
        save_token(sys.argv[2])
        print("[OK] Token 已保存")
        return

    token = get_token()
    if not token:
        print("=" * 50)
        print("  首次使用请设置 GitHub Personal Access Token")
        print("=" * 50)
        print()
        print("1. 打开 https://github.com/settings/tokens")
        print("2. 点 'Generate new token (classic)'")
        print("3. Note 填 'WWDmgCalc Preset Uploader'")
        print("4. Expiration 选 'No expiration'")
        print("5. 勾选 'repo' 权限")
        print("6. 点底部 'Generate token'")
        print("7. 复制生成的 token (ghp_开头)")
        print()
        print(f"然后运行: python tools/upload_presets.py --token 你的token")
        return

    print(f"仓库: {OWNER}/{REPO}")
    print(f"源目录: {PRESETS_DIR}")
    print()

    # 扫描本地文件
    manifest = build_manifest()
    total = sum(len(v) for v in manifest.values())
    print(f"本地共 {total} 个预设文件")
    for cat in CATEGORY_DIRS:
        files = manifest[cat]
        print(f"  {cat}/: {len(files)} 个")
        for f in files:
            print(f"    {f}")

    if total == 0:
        print("\n没有找到预设文件，退出。")
        return

    # ── 预检 ──
    print("\n正在预检...")
    errors = []
    # 1. 检查文件编码
    for cat in CATEGORY_DIRS:
        for fname in manifest[cat]:
            fpath = os.path.join(PRESETS_DIR, cat, fname)
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    f.read()
            except Exception:
                errors.append(f"  编码错误: {cat}/{fname}")
            # 检查文件名是否含特殊字符（除中文外）
            try:
                fname.encode("ascii")
            except UnicodeEncodeError:
                pass  # 含中文是正常的
    # 2. 检查 Token
    test_url = f"https://api.github.com/repos/{OWNER}/{REPO}"
    test_resp = github_api("GET", test_url)
    if test_resp is None:
        errors.append("  Token 无效或权限不足，请检查 GitHub Token 设置")
    else:
        print("  Token 有效")
    # 3. 检查文件权限（试 GET 第一个文件）
    if manifest:
        for cat in CATEGORY_DIRS:
            if manifest[cat]:
                test_path = f"presets/official/{cat}/{manifest[cat][0]}"
                test_file_url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{quote(test_path, safe='/')}"
                r = github_api("GET", test_file_url)
                if r is None:
                    # 文件不存在也可以创建，不报错
                    pass
                break
    
    if errors:
        print("\n预检发现以下问题：")
        print("\n".join(errors))
        print("请修复后重试。")
        return
    print("  通过")

    answer = input(f"\n确认上传 {total} 个文件到 GitHub？[y/N] ")
    if answer.lower() != "y":
        print("已取消")
        return


    # 上传预设文件
    success = 0
    failed = 0
    for cat in CATEGORY_DIRS:
        for fname in manifest[cat]:
            fpath = os.path.join(PRESETS_DIR, cat, fname)
            with open(fpath, "r", encoding="utf-8") as f:
                content = f.read()
            print(f"\n上传: {cat}/{fname} ...", end=" ")
            if upload_file(cat, fname, content):
                print("OK")
                success += 1
            else:
                print("失败")
                failed += 1

    # 上传 manifest.json（直接 PUT 到 presets/official/ 根目录）
    print(f"\n上传: manifest.json ...", end=" ")
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2)
    path = "presets/official/manifest.json"
    url = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{quote(path)}"
    data = {
        "message": "更新 manifest.json",
        "content": base64.b64encode(manifest_json.encode("utf-8")).decode("ascii"),
        "branch": BRANCH,
    }
    existing = github_api("GET", url)
    if existing and "sha" in existing:
        data["sha"] = existing["sha"]
    result = github_api("PUT", url, data)
    if result:
        print("OK")
    else:
        print("失败（不影响预设上传）")

    print()
    print("=" * 50)
    print(f"完成: 成功 {success}, 失败 {failed}")
    print(f"https://github.com/{OWNER}/{REPO}/tree/main/presets/official")
    print("=" * 50)


if __name__ == "__main__":
    main()
