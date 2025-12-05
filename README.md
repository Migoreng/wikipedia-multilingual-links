# wikipedia-multilingual-links


Wikipedia 多言語リンク抽出ツール

ブリッジ言語（ラテン語、英語など）を介して、異なる言語版Wikipedia記事の対応表を作成。
20以上の言語に対応し、Wikipediaダンプから多言語対応データセットを生成します。

Wikipedia Multilingual Links Extractor

Extract and merge cross-language Wikipedia article links through bridge languages (e.g., Latin, English). 
Supports 20+ languages and generates multilingual correspondence tables from Wikipedia dumps.

## 必要なモジュール

```bash
pip3 install tqdm requests
```

## 🚀 使用例

### 基本パターン

```bash
# 日本語-英語-ラテン語（従来と同じ）
python build_multilingual_wikipedia.py ja en --bridge la

# ドイツ語-英語-ラテン語
python build_multilingual_wikipedia.py de en --bridge la

# スペイン語-英語-ラテン語
python build_multilingual_wikipedia.py es en --bridge la
```

### 3言語以上

```bash
# 日本語-英語-ドイツ語-ラテン語
python build_multilingual_wikipedia.py ja en de --bridge la

# 5言語対応表
python build_multilingual_wikipedia.py ja en de fr es --bridge la
```

### ブリッジ言語を変更

```bash
# 英語をブリッジにして日本語-ドイツ語を対応
python build_multilingual_wikipedia.py ja de --bridge en
```

### オプション機能

```bash
# ダウンロード済みの場合はスキップ
python build_multilingual_wikipedia.py ja en --bridge la --skip-download

# パース済みCSVがある場合
python build_multilingual_wikipedia.py ja en --bridge la --skip-parse

# 出力ファイル名を指定
python build_multilingual_wikipedia.py de en --bridge la --output de_en_latin.csv
```

---

## 📋 対応言語（20言語以上）

- `en` (英語), `ja` (日本語), `de` (ドイツ語), `fr` (フランス語)
- `es` (スペイン語), `it` (イタリア語), `pt` (ポルトガル語)
- `ru` (ロシア語), `zh` (中国語), `ko` (韓国語)
- `ar` (アラビア語), `la` (ラテン語), `nl` (オランダ語)
- `pl` (ポーランド語), `sv` (スウェーデン語), `he` (ヘブライ語)
- `tr` (トルコ語), `cs` (チェコ語), `el` (ギリシャ語), `fi` (フィンランド語)

---

## ✨ 新機能

1. **コマンドライン引数対応** → 柔軟な指定が可能
2. **N言語マージ** → 2言語だけでなく、3言語以上も対応
3. **ブリッジ言語切り替え** → ラテン語以外も可能
4. **スキップオプション** → 部分的な再実行が可能
5. **エラーハンドリング** → ファイルがない場合も続行

---

## 備考
プログラムのコードは一切手で書いていません。Claude Sonnet 4.5で作成しました。
AIのプロバイダーはSider AIです。
Claudeに「どうすればラテン語と日本語と英語の辞書を実現できる？」というのを尋ねて、Bashでやり方を教えてもらいました。
その後何度も実行してはエラーが出て、その結果を返して分析してもらい、何度もスクリプトを修正してもらいました。
私はClaudeが教えてくれたとおりにスクリプトをコピペし、動作確認しただけです。
その後Bashだけでなく、他のOSでも動かせるように、Pythonに書き換えてもらい、開発中の複数のスクリプトも最終的に1つにまとめてもらいました。
何から何までClaude頼みでした。Bashの知識を少し持っていて、Pythonの知識はほぼゼロでしたが、ここまでできました。
挙句の果に、Readme.mdまで作ってくれました。
この作品は、AIでどこまでプログラムを作ったりできるのか具体的な一例になったものです。
