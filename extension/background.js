// ShopAssist – background.js
// Keeps the extension alive and handles optional badge updates

chrome.runtime.onInstalled.addListener(() => {
  console.log("ShopAssist installed.");
});
