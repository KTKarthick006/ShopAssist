// ShopAssist – content.js
// Extracts product name from the current Amazon / Flipkart page

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.type !== "GET_PRODUCT") return;

  const hostname = window.location.hostname;
  let name = null;

  try {
    if (hostname.includes("amazon")) {
      // Amazon product title
      const el =
        document.getElementById("productTitle") ||
        document.querySelector("h1.a-size-large") ||
        document.querySelector("span#title");
      name = el?.textContent?.trim() || null;

    } else if (hostname.includes("flipkart")) {
      // Flipkart product title
      const el =
        document.querySelector("span.B_NuCI") ||
        document.querySelector("h1.yhB1nd") ||
        document.querySelector("h1._9E25nV") ||
        document.querySelector("h1");
      name = el?.textContent?.trim() || null;
    }
  } catch (_) { /* silent */ }

  // Truncate very long names
  if (name && name.length > 120) name = name.slice(0, 120);

  sendResponse({ name });
  return true;
});
