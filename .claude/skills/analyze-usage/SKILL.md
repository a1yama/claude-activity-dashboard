---
description: 活動ログDBを分析し、CLAUDE.md・スキル・プロンプトの改善提案を生成する
user-invocable: true
---

# 活動ログ分析スキル

Claude Code の活動ログ DB を分析し、ワークフローの改善提案を生成します。

## 手順0: スキーマ確認（重要）

analyze.py を実行した後、**必ず最初にスキーマを確認**してください。これにより、フィールド名の推測によるエラーを防ぎます。

以下のPythonスクリプトで各カテゴリの実際のフィールド名を取得してください：

```python
import json

# analyze.py の出力ファイルパスを指定
with open('分析結果ファイルのパス', 'r') as f:
    data = json.load(f)

# 各カテゴリのスキーマを確認
for key in ['a1_bash_alternatives', 'a2_consecutive_tools', 'a3_tool_frequency',
            'b1_repeated_instructions', 'b2_user_messages', 'c1_fix_patterns',
            'c2_intent_mismatch', 'd1_project_efficiency', 'e1_long_sessions',
            'e2_hourly_activity']:
    if data[key] and len(data[key]) > 0:
        print(f"{key}: {list(data[key][0].keys())}")
```

### 標準スキーマ（参考）

以下は2026-03時点のスキーマです。将来変更される可能性があるため、**必ず手順0で実際のスキーマを確認**してください。

| カテゴリ | フィールド名 |
|---------|-------------|
| `a1_bash_alternatives` | `pattern`, `count`, `examples` |
| `a2_consecutive_tools` | `consecutive_tool`, `consecutive_count` |
| `a3_tool_frequency` | `tool_name`, `use_count` |
| `b1_repeated_instructions` | `instruction`, `repeat_count` |
| `b2_user_messages` | `content_preview` |
| `c1_fix_patterns` | `message`, `date_jst`, `project_name` |
| `c2_intent_mismatch` | `message`, `date_jst`, `project_name` |
| `d1_project_efficiency` | `project_name`, `sessions`, `user_msgs`, `tool_uses`, `tools_per_user_msg` |
| `e1_long_sessions` | `session_id`, `duration_minutes`, `message_count` |
| `e2_hourly_activity` | `hour_jst`, `message_count`, `tool_count` |

## 手順1: データ最新化と分析実行

`{{PROJECT_ROOT}}` はこのスキルファイルが属するプロジェクトのルートディレクトリです。

Bash で以下を **順番に** 実行してください:

```bash
cd {{PROJECT_ROOT}} && python3 ingest.py
```

```bash
cd {{PROJECT_ROOT}} && python3 analyze.py $ARGUMENTS
```

`analyze.py` は引数に応じて自動的にフィルタを適用します:
- 引数なし → 全期間分析
- `直近N日` / `last N days` → 期間フィルタ
- それ以外 → プロジェクト名フィルタ

出力は JSON 形式で、以下のキーを含みます:

| キー | 内容 |
|------|------|
| `basic_stats` | セッション数、メッセージ数、期間、プロジェクト数 |
| `a1_bash_alternatives` | Bash で実行されたが専用ツール（Read/Grep/Glob/Edit/Write）で代替可能なコマンド |
| `a2_consecutive_tools` | 同一ツールの連続実行パターン（Bash→Bash等） |
| `a3_tool_frequency` | 全ツールの使用頻度分布 |
| `b1_repeated_instructions` | 3回以上繰り返されたユーザー指示 |
| `b2_user_messages` | ユーザーメッセージ一覧（頻出キーワード抽出用） |
| `c1_fix_patterns` | 修正・やり直し系のメッセージ |
| `c2_intent_mismatch` | 否定表現を含む意図ズレ指示 |
| `d1_project_efficiency` | プロジェクト別のツール/ユーザーメッセージ比率 |
| `e1_long_sessions` | 所要時間TOP10セッション |
| `e2_hourly_activity` | 時間帯別の活動量 |

**次のステップ:** 手順0に進んで、スキーマ（各カテゴリのフィールド名）を確認してください。

## 手順2: レポート出力

**重要:** 手順0で確認したスキーマのフィールド名を使用してください。フィールド名を推測しないでください。

以下のPythonスクリプトで全カテゴリのレポートをマークダウン形式で出力してください：

```python
import json
import re
from collections import Counter

with open('分析結果ファイルのパス', 'r') as f:
    data = json.load(f)

# 基本統計
print('# 活動ログ分析レポート')
bs = data['basic_stats']
print(f"- セッション数: {bs['total_sessions']}")
# ... 以下、手順0で確認したフィールド名を使用して出力

# B-2: 頻出キーワード分析（AI分析）
all_text = ' '.join([msg['content_preview'] for msg in data['b2_user_messages'] if 'content_preview' in msg])
# 正規表現でキーワード抽出、Counter で集計
```

### レポート項目

1. 基本統計
2. A-1: Bash代替可能パターン
3. A-2: 連続ツール使用
4. A-3: ツール使用頻度
5. B-1: 繰り返し指示
6. B-2: 頻出キーワード（AI分析）
   - `b2_user_messages` の `content_preview` から、頻出する動詞・名詞・フレーズ（日本語・英語両方）を上位20個抽出
   - 単純な助詞・冠詞・前置詞は除外
7. C-1: 修正・やり直しパターン
8. C-2: 意図ズレ指示
9. D-1: プロジェクト別効率
10. E-1: 長期セッション
11. E-2: 時間帯別活動

データが0件のカテゴリは「該当データなし」と記載してください。

## 手順3: AI解釈と改善提案

レポートデータを基に、以下の3つの観点で **具体的な** 改善提案を生成してください。
各提案には番号を振ってください（後の手順で番号で選択するため）。

### 提案カテゴリ

**1. CLAUDE.md への追加推奨**
- Bash代替パターン（A-1）が多い場合 → 「Bashではなく専用ツールを使う」ルールの追加テキストを提案
- 繰り返し指示（B-1）が多い場合 → 繰り返しを減らすためのルール追加テキストを提案
- エラーパターン（C-1, C-2）の傾向から → 意図ズレを防ぐルール追加テキストを提案
- 具体的に `~/.claude/CLAUDE.md` またはプロジェクトの `.claude/CLAUDE.md` に追加すべきテキストを提示

**2. 新規スキル候補**
- 繰り返し指示（B-1）や頻出キーワード（B-2）から → スキル化すべき操作の提案
- ツール連続使用（A-2）から → 一連の操作をまとめるスキルの提案
- スキル名と概要を提示

**3. プロンプト改善（Claude側の振る舞いルールとして仕組み化）**

意図ズレパターン（C-2）や修正パターン（C-1）から、**ユーザーへのアドバイス**ではなく**Claude側の振る舞いルール**として CLAUDE.md に追記可能な形で提案する。

仕組み化の方針:
- 否定形の指示を受けた場合 → Claudeが肯定形に言い換えて確認するルール
- 曖昧な指示を受けた場合 → Claudeが着手前に要件を確認するルール
- 長期セッション → Claudeがセッション分割を提案するルール

各提案は以下の形式で出力してください:

```
### 改善提案

#### CLAUDE.md への追加推奨
1. [提案タイトル]
   - 根拠: [データからの根拠]
   - 追加テキスト:
   ```
   追加すべき具体的なテキスト
   ```
   - 対象ファイル: ~/.claude/CLAUDE.md または .claude/CLAUDE.md

2. ...

#### 新規スキル候補
3. [スキル名]
   - 根拠: [データからの根拠]
   - 概要: [スキルの説明]

4. ...

#### プロンプト改善（CLAUDE.md ルールとして反映）
5. [改善ポイント]
   - 根拠: [データからの根拠]
   - Claudeの振る舞いルール:
   ```
   CLAUDE.mdに追加するルールテキスト
   ```
   - 対象ファイル: ~/.claude/CLAUDE.md または .claude/CLAUDE.md
   - 参考（ユーザー向けアドバイス）: [任意。ユーザー自身が改善できるポイントがあれば補足]

6. ...
```

## 手順4: 反映サポート

改善提案を出力した後、ユーザーに以下のように確認してください:

```
どの提案を反映しますか？番号で選択してください（複数可、例: 1,3,5）。
「なし」で終了します。
```

ユーザーが番号を選択した場合、以下の手順で反映してください:

### CLAUDE.md 修正の場合
1. 対象ファイル（`~/.claude/CLAUDE.md` またはプロジェクトの `.claude/CLAUDE.md`）を Read で読み込む
2. 適切な箇所を特定し、追加テキストを Edit で追記
3. 反映前に差分を表示して最終確認

### スキル新規作成の場合
1. `.claude/skills/{スキル名}/SKILL.md` を Write で作成
2. 作成内容を表示

### 既存スキル修正の場合
1. 対象スキルの SKILL.md を Read で読み込む
2. Edit で修正
3. 反映前に差分を表示して最終確認

反映完了後、変更内容のサマリーを表示してください。
