# storyflow-d3

## 概要

`storyflow-d3`は、論文「[StoryFlow: Tracking the Evolution of Stories](http://research.microsoft.com/en-us/um/people/yangliu/publication/storyflow.pdf)」で提案されたストーリーライン可視化アルゴリズムをベースに、[D3.js](http://d3js.org/)で再実装・改変したリポジトリです。

本研究では、StoryFlowのレイアウト生成手法を一部改変し、既存手法の構造を維持しながら新しいレイアウト作成プロセスを検証しています。

このリポジトリには、元となる `storyflow-d3` のコードを改変した部分が含まれています。オリジナルの `storyflow-d3` に起源を持つコードについては、元作者の権利が残る場合があります。

## 目的

- StoryFlowアルゴリズムの理解と再現
- D3.jsを用いたインタラクティブな可視化の実装
- 研究発表・論文補助資料としての利用

## 特徴

- D3.jsベースのストーリーライン可視化
- Tanahashi氏公開のストーリーデータをJSONに変換して利用
- 複数のデモHTMLファイルを含み、異なる可視化パラメータやレイアウトを確認可能

## 含まれるファイル

- `index.html` - 基本的なStoryFlowデモ
- `index_region.html` / `index_region_alpha_demo.html` / `index_region_alt.html` - 領域配置や透明度に関するデモ
- `index_tradeoff.html` / `index_tradeoff_strong.html` - トレードオフ検証用のデモ
- `dataset/` - 利用した元データと変換済みデータ
- `lib/` - 可視化用ライブラリ/コード
- `osqp/` - 必要に応じた最適化ライブラリ関連
- `a.json` - おそらく追加のデータまたは設定ファイル

## 動作確認方法

1. リポジトリをクローンまたはダウンロードする
2. ブラウザでルートの `index.html` または `index_region_alpha_demo.html` などを開く

> ローカルファイルから開いた場合、ブラウザのセキュリティ制限で読み込みが失敗する場合があります。必要に応じて簡易HTTPサーバーを立ててください。

```bash
cd storyflow-d3
python3 -m http.server 8000
```

その後、ブラウザで `http://localhost:8000/` にアクセスします。

## 参考資料

- `StoryFlow: Tracking the Evolution of Stories` by Y. Liu, J. Heer, M. Agrawala
- Yuzuru Tanahashi氏のストーリーラインデータ: http://vis.cs.ucdavis.edu/~tanahashi/

## 研究・発表用途

このリポジトリは、可視化手法の実装例として研究成果や発表資料に利用できます。論文やレポートに組み込む際は、オリジナルのStoryFlow論文とデータの出典を明示してください。

- 本研究の成果は `paper.pdf` にまとめられています。

## ライセンス

このリポジトリ自体は `LICENSE` ファイルの条件に従います。オリジナルのStoryFlow論文や外部データの利用についても、各出典元のライセンス条件を確認してください。
