#!/usr/bin/env python3
"""
Wikipedia 多言語対応表作成パイプライン
- 任意の言語ペアに対応
- コマンドライン引数でカスタマイズ可能
- 3言語以上の組み合わせにも対応
"""

import os
import sys
import gzip
import csv
import argparse
import requests
from pathlib import Path
from collections import defaultdict
from tqdm import tqdm


# ========================================
# 言語コード → 表示名のマッピング
# ========================================

LANGUAGE_NAMES = {
    'en': '英語',
    'ja': '日本語',
    'de': 'ドイツ語',
    'fr': 'フランス語',
    'es': 'スペイン語',
    'it': 'イタリア語',
    'pt': 'ポルトガル語',
    'ru': 'ロシア語',
    'zh': '中国語',
    'ko': '韓国語',
    'ar': 'アラビア語',
    'la': 'ラテン語',
    'nl': 'オランダ語',
    'pl': 'ポーランド語',
    'sv': 'スウェーデン語',
    'he': 'ヘブライ語',
    'tr': 'トルコ語',
    'cs': 'チェコ語',
    'el': 'ギリシャ語',
    'fi': 'フィンランド語',
}


# ========================================
# 1. ダウンロード機能
# ========================================

def download_file(url, output_path, chunk_size=8192):
    """
    HTTP GETでファイルをダウンロード（進捗バー付き、レジューム対応）
    """
    output_path = Path(output_path)
    
    # すでに完全にダウンロード済みかチェック
    headers = {}
    if output_path.exists():
        existing_size = output_path.stat().st_size
        headers['Range'] = f'bytes={existing_size}-'
        print(f"📂 既存ファイル検出: {output_path.name} ({existing_size:,} bytes)")
        print(f"   → 途中から再開します")
    
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=30)
    except requests.exceptions.RequestException as e:
        print(f"❌ ダウンロードエラー: {e}")
        return False
    
    # 206 Partial Content または 200 OK
    if response.status_code == 416:  # Range Not Satisfiable = すでに完了
        print(f"✅ {output_path.name} はすでにダウンロード済みです")
        return True
    
    if response.status_code not in (200, 206):
        print(f"❌ HTTPエラー {response.status_code}: {url}")
        return False
    
    total_size = int(response.headers.get('content-length', 0))
    mode = 'ab' if response.status_code == 206 else 'wb'
    
    print(f"📥 ダウンロード開始: {output_path.name}")
    
    with open(output_path, mode) as f, tqdm(
        total=total_size,
        initial=output_path.stat().st_size if mode == 'ab' else 0,
        unit='B',
        unit_scale=True,
        unit_divisor=1024,
    ) as pbar:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                pbar.update(len(chunk))
    
    print(f"✅ ダウンロード完了: {output_path.name}\n")
    return True


def download_wikipedia_dumps(lang):
    """
    Wikipedia dumps (langlinks + page) をダウンロード
    """
    base_url = f"https://dumps.wikimedia.org/{lang}wiki/latest/"
    files = [
        f"{lang}wiki-latest-langlinks.sql.gz",
        f"{lang}wiki-latest-page.sql.gz"
    ]
    
    lang_name = LANGUAGE_NAMES.get(lang, lang.upper())
    print(f"{'='*60}")
    print(f"Wikipedia {lang_name} ({lang}) ダンプダウンロード")
    print(f"{'='*60}\n")
    
    for filename in files:
        url = base_url + filename
        success = download_file(url, filename)
        if not success:
            print(f"⚠️  {filename} のダウンロードに失敗しました")
            return False
    
    return True


# ========================================
# 2. パース機能
# ========================================

def parse_sql_insert(line):
    """
    INSERT INTO文から値部分を抽出
    """
    if not line.startswith('INSERT INTO'):
        return []
    
    start = line.find('VALUES') + 6
    if start == 5:
        return []
    
    values_str = line[start:].rstrip(';\n')
    rows = []
    depth = 0
    current = []
    field = ''
    in_quote = False
    escape_next = False
    
    for char in values_str:
        if escape_next:
            field += char
            escape_next = False
            continue
        
        if char == '\\':
            escape_next = True
            field += char
            continue
        
        if char == "'" and not escape_next:
            in_quote = not in_quote
            continue
        
        if in_quote:
            field += char
            continue
        
        if char == '(':
            depth += 1
            if depth == 1:
                current = []
            continue
        
        if char == ')':
            depth -= 1
            if depth == 0:
                if field:
                    current.append(field)
                    field = ''
                if current:
                    rows.append(tuple(current))
            continue
        
        if char == ',' and depth == 1:
            current.append(field)
            field = ''
            continue
        
        if depth == 1:
            field += char
    
    return rows


def parse_wikipedia_dump(source_lang, target_lang):
    """
    Wikipediaダンプから指定言語へのリンクを抽出
    """
    source_name = LANGUAGE_NAMES.get(source_lang, source_lang.upper())
    target_name = LANGUAGE_NAMES.get(target_lang, target_lang.upper())
    
    print(f"\n{'='*60}")
    print(f"Wikipedia {source_name} ({source_lang}) → {target_name} ({target_lang}) パース開始")
    print(f"{'='*60}\n")
    
    langlinks_file = f"{source_lang}wiki-latest-langlinks.sql.gz"
    page_file = f"{source_lang}wiki-latest-page.sql.gz"
    output_file = f"{source_lang}_{target_lang}_all.csv"
    
    # ファイル存在チェック
    if not Path(langlinks_file).exists():
        print(f"❌ エラー: {langlinks_file} が見つかりません")
        return None
    if not Path(page_file).exists():
        print(f"❌ エラー: {page_file} が見つかりません")
        return None
    
    # ステップ1: langlinks から対象言語リンクを抽出
    print(f"ステップ1: {langlinks_file} 読み込み中...")
    page_to_target = {}
    
    with gzip.open(langlinks_file, 'rt', encoding='utf-8', errors='ignore') as f:
        for line in tqdm(f, desc="langlinks処理"):
            rows = parse_sql_insert(line)
            for row in rows:
                if len(row) >= 3 and row[1] == target_lang:
                    page_id = row[0]
                    target_title = row[2]
                    page_to_target[page_id] = target_title
    
    print(f"  → {len(page_to_target):,} 件の{target_name}リンクを検出\n")
    
    if len(page_to_target) == 0:
        print(f"⚠️  警告: {target_name}へのリンクが見つかりませんでした")
        return None
    
    # ステップ2: page からタイトルを取得
    print(f"ステップ2: {page_file} 読み込み中...")
    results = []
    
    with gzip.open(page_file, 'rt', encoding='utf-8', errors='ignore') as f:
        for line in tqdm(f, desc="page処理"):
            rows = parse_sql_insert(line)
            for row in rows:
                if len(row) >= 3:
                    page_id = row[0]
                    namespace = row[1]
                    title = row[2]
                    
                    if namespace == '0' and page_id in page_to_target:
                        results.append({
                            'page_id': page_id,
                            source_lang: title,
                            target_lang: page_to_target[page_id]
                        })
    
    print(f"  → {len(results):,} 件のマッチング完了\n")
    
    # ステップ3: CSV出力
    print(f"ステップ3: {output_file} に保存中...")
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['page_id', source_name, target_name]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for item in results:
            writer.writerow({
                'page_id': item['page_id'],
                source_name: item[source_lang],
                target_name: item[target_lang]
            })
    
    print(f"✅ 完了: {output_file} ({len(results):,} 件)\n")
    return output_file


# ========================================
# 3. マージ機能（N言語対応）
# ========================================

def merge_languages(lang_files, bridge_lang, output_file):
    """
    複数の言語ファイルをブリッジ言語でマージ
    
    Args:
        lang_files: [(lang_code, csv_file), ...] のリスト
        bridge_lang: ブリッジ言語コード（例: 'la', 'en'）
        output_file: 出力ファイル名
    """
    bridge_name = LANGUAGE_NAMES.get(bridge_lang, bridge_lang.upper())
    
    print(f"{'='*60}")
    print(f"多言語マージ（ブリッジ: {bridge_name}）")
    print(f"{'='*60}\n")
    
    # 各言語ファイルをインデックス化
    all_data = {}
    lang_names = []
    
    for lang_code, csv_file in lang_files:
        lang_name = LANGUAGE_NAMES.get(lang_code, lang_code.upper())
        lang_names.append((lang_code, lang_name))
        
        print(f"ステップ: {csv_file} 読み込み中...")
        
        if not Path(csv_file).exists():
            print(f"⚠️  警告: {csv_file} が見つかりません。スキップします。")
            continue
        
        with open(csv_file, encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                # ブリッジ言語の値を取得
                bridge_value = None
                lang_value = None
                
                for key, value in row.items():
                    if bridge_name in key or bridge_lang in key.lower():
                        bridge_value = value.strip()
                    elif lang_name in key or lang_code in key.lower():
                        lang_value = value.strip()
                
                if bridge_value and lang_value:
                    if bridge_value not in all_data:
                        all_data[bridge_value] = {}
                    
                    if lang_code not in all_data[bridge_value]:
                        all_data[bridge_value][lang_code] = []
                    
                    if lang_value not in all_data[bridge_value][lang_code]:
                        all_data[bridge_value][lang_code].append(lang_value)
        
        total_entries = sum(len(v.get(lang_code, [])) for v in all_data.values())
        print(f"  → {total_entries:,} 件読み込み\n")
    
    # マージ結果を構築
    print("ステップ: マージ処理中...")
    merged = []
    
    for bridge_value, lang_dict in all_data.items():
        # すべての言語でデータがあるもののみ
        if len(lang_dict) == len(lang_files):
            # 各言語の組み合わせを生成
            from itertools import product
            combinations = product(*[lang_dict[lc] for lc, _ in lang_names])
            
            for combo in combinations:
                row = {LANGUAGE_NAMES.get(lc, lc): val for (lc, _), val in zip(lang_names, combo)}
                row[bridge_name] = bridge_value
                merged.append(row)
    
    print(f"  → {len(merged):,} 件のマッチング完了\n")
    
    # 重複削除
    print("ステップ: 重複削除中...")
    seen = set()
    unique_merged = []
    
    for item in merged:
        key = tuple(item.values())
        if key not in seen:
            seen.add(key)
            unique_merged.append(item)
    
    print(f"  → 重複削除後: {len(unique_merged):,} 件\n")
    
    # ソート & 保存
    unique_merged.sort(key=lambda x: x[bridge_name])
    
    print(f"ステップ: {output_file} に保存中...")
    
    # フィールド名を決定（ブリッジ言語を最後に）
    fieldnames = [LANGUAGE_NAMES.get(lc, lc) for lc, _ in lang_names]
    if bridge_name not in fieldnames:
        fieldnames.append(bridge_name)
    else:
        fieldnames.remove(bridge_name)
        fieldnames.append(bridge_name)
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(unique_merged)
    
    print(f"✅ 完了: {output_file} ({len(unique_merged):,} 件)\n")
    
    # サンプル表示
    if unique_merged:
        print("結果サンプル（最初の10件）:")
        print("-" * 100)
        print(" | ".join(f"{fn:30}" for fn in fieldnames))
        print("-" * 100)
        for item in unique_merged[:10]:
            print(" | ".join(f"{item.get(fn, ''):30}" for fn in fieldnames))
    
    return output_file


# ========================================
# 4. メイン処理
# ========================================

def main():
    parser = argparse.ArgumentParser(
        description='Wikipedia 多言語対応表作成パイプライン',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用例:
  # 日本語-英語-ラテン語
  python build_multilingual_wikipedia.py ja en --bridge la
  
  # ドイツ語-英語-ラテン語
  python build_multilingual_wikipedia.py de en --bridge la
  
  # スペイン語-フランス語-イタリア語-ラテン語
  python build_multilingual_wikipedia.py es fr it --bridge la
  
  # ダウンロードのみスキップ（すでにダウンロード済みの場合）
  python build_multilingual_wikipedia.py ja en --bridge la --skip-download
  
対応言語コード:
  en (英語), ja (日本語), de (ドイツ語), fr (フランス語), 
  es (スペイン語), it (イタリア語), pt (ポルトガル語), 
  ru (ロシア語), zh (中国語), ko (韓国語), ar (アラビア語),
  la (ラテン語), nl (オランダ語), pl (ポーランド語), など
        """
    )
    
    parser.add_argument(
        'languages',
        nargs='+',
        help='処理する言語コード（例: ja en de）'
    )
    
    parser.add_argument(
        '--bridge',
        default='la',
        help='ブリッジ言語コード（デフォルト: la [ラテン語]）'
    )
    
    parser.add_argument(
        '--output',
        help='出力ファイル名（デフォルト: 自動生成）'
    )
    
    parser.add_argument(
        '--skip-download',
        action='store_true',
        help='ダウンロードをスキップ'
    )
    
    parser.add_argument(
        '--skip-parse',
        action='store_true',
        help='パースをスキップ（CSVファイルがすでにある場合）'
    )
    
    args = parser.parse_args()
    
    languages = args.languages
    bridge_lang = args.bridge
    
    # 出力ファイル名の自動生成
    if args.output:
        output_file = args.output
    else:
        lang_part = '_'.join(languages)
        output_file = f"{lang_part}_{bridge_lang}_all.csv"
    
    print("\n" + "="*60)
    print("Wikipedia 多言語対応表 作成パイプライン")
    print("="*60)
    print(f"対象言語: {', '.join([LANGUAGE_NAMES.get(l, l) for l in languages])}")
    print(f"ブリッジ言語: {LANGUAGE_NAMES.get(bridge_lang, bridge_lang)}")
    print(f"出力ファイル: {output_file}")
    print("="*60 + "\n")
    
    # 1. ダウンロード
    if not args.skip_download:
        print("【フェーズ1】ダウンロード\n")
        for lang in languages:
            success = download_wikipedia_dumps(lang)
            if not success:
                print(f"⚠️  {lang} のダウンロードに失敗しました。続行します...")
    else:
        print("【フェーズ1】ダウンロード - スキップ\n")
    
    # 2. パース
    if not args.skip_parse:
        print("\n【フェーズ2】パース\n")
        for lang in languages:
            result = parse_wikipedia_dump(lang, bridge_lang)
            if not result:
                print(f"⚠️  {lang} のパースに失敗しました。続行します...")
    else:
        print("\n【フェーズ2】パース - スキップ\n")
    
    # 3. マージ
    print("\n【フェーズ3】マージ\n")
    lang_files = [(lang, f"{lang}_{bridge_lang}_all.csv") for lang in languages]
    merge_languages(lang_files, bridge_lang, output_file)
    
    print("\n" + "="*60)
    print("🎉 すべての処理が完了しました！")
    print("="*60)
    print(f"\n最終成果物: {output_file}")


if __name__ == "__main__":
    main()

