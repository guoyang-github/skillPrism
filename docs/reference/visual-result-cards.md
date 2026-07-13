# 视觉成果卡片

skillPrism 提供一个可选的视觉成果卡片生成器，用于展示单次优化的前后对比。

## 生成卡片

```bash
python examples/reporters/visual_result_card.py \
  --input artifacts/<skill>/baseline/optimization_result.json \
  --output result-card.html
```

## 截图（需安装 playwright）

```bash
pip install playwright
playwright install

python examples/reporters/visual_result_card.py \
  --input artifacts/<skill>/baseline/optimization_result.json \
  --output result-card.html \
  --screenshot
```

## 模板

HTML 模板位于 `templates/skill_standard/result-card.html`，可自定义品牌样式。

## 说明

视觉卡片是可选 reporter，不进入核心引擎。它读取优化结果 JSON，生成可分享的 HTML/PNG。
