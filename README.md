# storyflow-d3

## 概要

`storyflow-d3`は、論文「[StoryFlow: Tracking the Evolution of Stories](http://research.microsoft.com/en-us/um/people/yangliu/publication/storyflow.pdf)」で提案されたストーリーライン可視化アルゴリズムをベースに、[D3.js](http://d3js.org/)で再実装・改変したリポジトリです。

本研究では、StoryFlowのレイアウト生成手法を一部改変し、既存手法の構造を維持しながら新しいレイアウト作成プロセスを検証しています。

このリポジトリには、元となる `storyflow-d3` のコードを改変した部分が含まれています。オリジナルの `storyflow-d3` に起源を持つコードについては、元作者の権利が残る場合があります。

## 研究概要

本研究は、ストーリーライン可視化のレイアウトを「高速かつ階層構造に対応できる最適化問題」として定式化し、既存のStoryFlow手法を拡張します。

主な特徴:

- 離散最適化による初期レイアウト生成と、連続二次最適化によるレイアウト改善を組み合わせたハイブリッド最適化
- セッション（同時刻に交互作用するエンティティ群）とエンティティ直線の順序・整列を反復的に調整
- 階層化されたロケーション構造を考慮し、時間軸に沿った階層情報を視覚的に表現
- マルチレベルの詳細度（LOD）レンダリングにより、数千本規模のエンティティ線を扱えるスケーラビリティを実現
- リアルタイムな対話操作（追加・削除、ドラッグ、ストレート化、バンドリング）を可能にする効率性

論文 `paper.pdf` では、レイアウトの美的基準として「線の交差、線の揺れ、揺れ距離、余白」の最小化を重視し、同時に「隣接配置」と「階層ロケーション」を満たす制約を導入しています。

## 目的

- StoryFlowアルゴリズムの理解と再現
- D3.jsを用いたインタラクティブな可視化の実装
- 研究発表・論文補助資料としての利用

## 特徴

- D3.jsベースのストーリーライン可視化
- Tanahashi氏公開のストーリーデータをJSONに変換して利用
- 複数のデモHTMLファイルを含み、異なる可視化パラメータやレイアウトを確認可能

## 公開デモ

- 実際のデモページ: https://on6848.github.io/storyline_b4/index_region_alpha_demo.html

このリンクを開くと `index_region_alpha_demo.html` が実行され、閲覧者が直接可視化を体験できます。

## 動作確認方法

### 公開ページで見る

1. `https://on6848.github.io/storyline_b4/index_region_alpha_demo.html` を開きます
2. `index_region_alpha_demo.html` のインタラクティブな画面で、データ切り替えやパラメータ調整を体験します

### ローカルで見る

1. リポジトリをクローンまたはダウンロードする
2. ターミナルでリポジトリのルートに移動する

```bash
cd storyflow-d3
python3 -m http.server 8000
```

3. ブラウザで以下にアクセスする

- `http://localhost:8000/index_region_alpha_demo.html`
- `http://localhost:8000/index.html`

> 直接 `file://` で開くと、ブラウザのセキュリティ制限によりデータの読み込みが失敗する場合があります。HTTPサーバーを使うのが推奨です。

## `index_region_alpha_demo.html` の操作方法

- `データセット` ドロップダウン
  - `市区町村セッション（αデモ）` / `都道府県セッション（αデモ）` / `地方セッション（αデモ）` を選択し、異なる階層での配置を確認します
- `interpolation` ドロップダウン
  - 線の補間方法を変更できます（Linear / Step / Basis / Bundle / Cardinal / Monotone など）
- `Redraw All` ボタン
  - 現在の設定に応じて全体レイアウトを再描画します
- `Plot Tradeoff` ボタン
  - 現在のパラメータで交差数と配置安定性のトレードオフを解析して表示します
- `LOD バンドリング` チェックボックス
  - レベルオブディティールによるバンドリングを有効にして、重なりを抑えた描画を試せます
- `配置一貫性重み` スライダー
  - レイアウトの時間的一貫性をどれだけ重視するかを調整します。値を大きくするほど、前後ステップ間の配置変化が抑えられます

## `index_region_alpha_demo.html` が描画する内容

- 上部コントロールでデータセットと補間方法を選択できます
- `スケール間比較` パネル
  - 同一時刻における順位差（Kendall距離）を計算し、都市・県・地方のレイアウト差を比較します
- `トレードオフ` パネル
  - `配置一貫性重み` を変化させたときの、交差数と配置変化率の関係を可視化します
- 中央のキャンバス領域
  - ストーリーラインの線やラベルを時間軸に沿って配置し、データの変化とレイアウトの違いを直感的に示します

## 含まれるファイル

- `index.html` - 基本的なStoryFlowデモ
- `index_region.html` - 地方スケールのStoryFlowレイアウト
- `index_region_alpha_demo.html` - スケール間比較とトレードオフを示すαデモ
- `index_region_alt.html` - 地方レイアウトの別バリエーション
- `index_tradeoff.html` - パラメータによる交差数・安定性のトレードオフ検証
- `index_tradeoff_strong.html` - 強調したトレードオフ検証デモ
- `index_extra.html` - 交差を多く含む別ページ
- `dataset/` - 利用した元データと変換済みデータ
- `lib/` - 可視化用ライブラリ/コード
- `osqp/` - 最適化ライブラリ関連
- `a.json` - 追加のデータまたは設定ファイル

## 各デモの目的

- `index.html`
  - StoryFlowの基本的な可視化を確認するための標準デモ
- `index_region.html`
  - 地方規模のレイアウト手法を検証するデモ
- `index_region_alpha_demo.html`
  - 複数階層での比較とトレードオフ分析を目的としたα版デモ
- `index_region_alt.html`
  - 同じ地方データに対する別構成のレイアウトバリエーション
- `index_tradeoff.html`
  - 目的関数の重みやパラメータ変更が交差数・安定性に与える影響を可視化するページ
- `index_tradeoff_strong.html`
  - より明確にパラメータトレードオフを示す強調版デモ
- `index_extra.html`
  - 交差の多いレイアウトを比較し、可視化手法の制約を確認するための別ページ

## 参考資料

- `StoryFlow: Tracking the Evolution of Stories` by Y. Liu, J. Heer, M. Agrawala
- Yuzuru Tanahashi氏のストーリーラインデータ: http://vis.cs.ucdavis.edu/~tanahashi/

## 研究・発表用途

このリポジトリは、可視化手法の実装例として研究成果や発表資料に利用できます。論文やレポートに組み込む際は、オリジナルのStoryFlow論文とデータの出典を明示してください。

- 本研究の成果は `paper.pdf` にまとめられています。

## ライセンス

このリポジトリ自体は `LICENSE` ファイルの条件に従います。オリジナルのStoryFlow論文や外部データの利用についても、各出典元のライセンス条件を確認してください。
