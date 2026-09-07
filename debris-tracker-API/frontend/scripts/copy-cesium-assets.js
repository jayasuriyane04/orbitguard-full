/**
 * Copies Cesium's static Assets/Workers/Widgets/ThirdParty into public/cesium
 * so they're served as plain static files, independent of whatever bundler
 * (webpack or turbopack) Next.js uses -- CopyWebpackPlugin-style approaches
 * are not reliable across both, so this sidesteps the bundler entirely.
 * Runs automatically via the "postinstall" script in package.json.
 */
const fs = require("fs");
const path = require("path");

const SRC = path.join(__dirname, "..", "node_modules", "cesium", "Build", "Cesium");
const DEST = path.join(__dirname, "..", "public", "cesium");
const DIRS_TO_COPY = ["Assets", "ThirdParty", "Widgets", "Workers"];

function copyRecursive(src, dest) {
  fs.mkdirSync(dest, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const srcPath = path.join(src, entry.name);
    const destPath = path.join(dest, entry.name);
    if (entry.isDirectory()) {
      copyRecursive(srcPath, destPath);
    } else {
      fs.copyFileSync(srcPath, destPath);
    }
  }
}

if (!fs.existsSync(SRC)) {
  console.warn("[copy-cesium-assets] cesium package not found, skipping");
  process.exit(0);
}

for (const dir of DIRS_TO_COPY) {
  const srcDir = path.join(SRC, dir);
  const destDir = path.join(DEST, dir);
  if (fs.existsSync(srcDir)) {
    copyRecursive(srcDir, destDir);
  }
}

console.log("[copy-cesium-assets] Cesium static assets copied to public/cesium");
