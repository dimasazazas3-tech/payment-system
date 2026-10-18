// Копіює адреси (Ignition) та ABI (artifacts) у папку python/
const fs = require("fs");
const path = require("path");

const chainId = process.argv[2] || "31337";
const root = path.join(__dirname, "..");
const addrFile = path.join(root, "ignition", "deployments", `chain-${chainId}`, "deployed_addresses.json");
const outDir = path.join(root, "python");
const abiDir = path.join(outDir, "abi");

const deployed = JSON.parse(fs.readFileSync(addrFile, "utf8"));
const names = ["FeeCollector", "PaymentProcessor"];

fs.mkdirSync(abiDir, { recursive: true });
const addresses = {};
for (const name of names) {
  addresses[name] = deployed[`PaymentSystemModule#${name}`];
  const artifact = require(path.join(root, "artifacts", "contracts", `${name}.sol`, `${name}.json`));
  fs.writeFileSync(path.join(abiDir, `${name}.json`), JSON.stringify(artifact.abi, null, 2));
}
fs.writeFileSync(path.join(outDir, "contracts.json"), JSON.stringify(addresses, null, 2));
console.log("Експортовано:", addresses);
