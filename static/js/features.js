document.addEventListener("DOMContentLoaded", () => {
  // Add a lazy-loading hint to product imagery that does not specify one.
  document.querySelectorAll(".product-grid img, .product-gallery img").forEach((img) => {
    if (!img.hasAttribute("loading")) img.setAttribute("loading", "lazy");
    if (!img.hasAttribute("decoding")) img.setAttribute("decoding", "async");
  });
});
