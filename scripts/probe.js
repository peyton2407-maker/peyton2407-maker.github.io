async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const bar = document.getElementById("tabBar");
  const g = typeof subnavGroupNow === "function" ? subnavGroupNow() : null;
  return { width: innerWidth, hasFix: typeof subnavArrows === "function", drag: String(typeof subnavArrows === "function" ? subnavArrows : "").includes("dragstart"),
    overflow: g ? g.scrollWidth - g.clientWidth : null, rightArrow: bar && bar.__right ? !bar.__right.hidden : null };
}
