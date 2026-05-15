# portfolio-manager-sample

ポートフォリオ管理 / 日産PSR分析ダッシュボード（Streamlit）。

担保=配当3銘柄、被担保=日産自動車。LTV 55-60%目標で日産を年1,000万ペースで買い増す運用を、
余力メーター・DOE配当シナリオ・日産PSR分析の3セクションで可視化します。

> ⚠️ サンプルデータです。銘柄・株数・借入額などはすべてサンプル値で、投資助言ではありません。

## 機能

- **01 ポートフォリオ管理** — 保有銘柄の時価、LTV、しきい値（60/70/85%）進捗
- **02 DOE配当シナリオ** — 配当成長・借り増し・日産買い増しの時系列シミュレーション
- **03 日産自動車分析** — FY25実績〜FY27想定のPSR/PER評価、Re:Nissanシナリオ

## 株価データ

[みんかぶ](https://minkabu.jp) から4銘柄の株価をスクレイピング（15分キャッシュ）。
取得失敗時は `app.py` 内の `fallback_price` に自動フォールバックします。

> Streamlit Community Cloud は海外サーバーで稼働するため、みんかぶ側でアクセスが
> 制限されると株価がフォールバック値（固定）になる場合があります。

## ローカル実行

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud へのデプロイ

1. [share.streamlit.io](https://share.streamlit.io) にGitHubアカウントでサインイン
2. **New app** → このリポジトリ / ブランチ `main` / Main file path `app.py` を指定
3. **Deploy** をクリック

テーマ設定は `.streamlit/config.toml` から自動的に読み込まれます。
