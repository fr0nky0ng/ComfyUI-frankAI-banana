import { app } from "/scripts/app.js";

app.registerExtension({
	name: "FrankAI.BananaPromptSelector.Final",

	async nodeCreated(node) {
		if (node.comfyClass !== "BananaPromptSelector") {
			return;
		}

		// 為了確保穩定，我們在節點完全初始化後再執行我們的邏輯
		setTimeout(() => {
			console.log("[FrankAI Final] 節點已創建，開始設置回調...");

			const titleWidget = node.widgets.find(w => w.name === "title");
			const promptWidget = node.widgets.find(w => w.name === "prompt");

			if (!titleWidget || !promptWidget) {
				console.error("[FrankAI Final] 錯誤：找不到 title 或 prompt widget！");
				return;
			}

			// 將 promptsData 緩存在閉包中，避免重複獲取
			let promptsData = null;

			const getPromptsData = async () => {
				if (promptsData) return promptsData; // 如果已緩存，直接返回
				try {
					const response = await fetch("/frankai/get_prompts");
					if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
					promptsData = await response.json();
					console.log("[FrankAI Final] 已成功獲取並緩存 prompts data。");
					return promptsData;
				} catch (e) {
					console.error("[FrankAI Final] 獲取 prompts data 失敗!", e);
					promptsData = []; // 設置為空陣列以防再次嘗試
					return promptsData;
				}
			};

			const updatePromptForTitle = (selectedTitle) => {
				if (!promptsData || !promptWidget.inputEl) {
					console.warn("[FrankAI Final] Data 或 UI 尚未準備好，無法更新。");
					return;
				}
				
				const selectedItem = promptsData.find(item => item.title === selectedTitle);
				const newPrompt = selectedItem ? selectedItem.prompt : "";

				// **核心更新邏輯**
				// 1. 更新 widget 的內部值
				promptWidget.value = newPrompt;
				// 2. 直接更新可見的 HTML <textarea> 元素的值
				promptWidget.inputEl.value = newPrompt;
				
				console.log(`[FrankAI Final] Prompt UI 已更新為: "${newPrompt.substring(0, 30)}..."`);
			};

			// --- 使用 ComfyUI 原生的回調機制 ---
			// 1. 保存原始的回調函數（如果有）
			const originalTitleCallback = titleWidget.callback;

			// 2. 覆寫為我們自己的異步回調函數
			titleWidget.callback = async (value) => {
				// 如果有原始的回調，先執行它
				if (originalTitleCallback) {
					originalTitleCallback.call(titleWidget, value);
				}
				
				console.log(`[FrankAI Final] Title 回調觸發，值: ${value}`);

				// 確保數據已經被獲取
				await getPromptsData();
				
				// 執行我們的更新邏輯
				updatePromptForTitle(value);
			};

			// 3. 初始觸發一次，以設置節點的初始狀態
			// 我們需要先獲取數據，然後再觸發回調
			getPromptsData().then(() => {
				if (titleWidget.value) {
					console.log("[FrankAI Final] 正在執行初始 UI 設置...");
					// 手動調用一次回調函數來同步初始狀態
					titleWidget.callback(titleWidget.value);
				}
			});

		}, 100); // 延遲 100 毫秒等待節點完全初始化
	}
});