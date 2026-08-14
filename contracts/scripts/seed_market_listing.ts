import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function main() {
  const depFile = path.join(__dirname, "..", "deployments", "baseSepolia.json");
  const dep = JSON.parse(fs.readFileSync(depFile, "utf8"));

  const [deployer] = await ethers.getSigners();
  const market = await ethers.getContractAt("SoundHubMarket", dep.market);

  const existing = await market.nextListingId();
  if (existing > 1n) {
    console.log(`Marketplace already has ${Number(existing) - 1} listing(s) — skipping seed.`);
    return;
  }

  const tx = await market.list(
    "Neon Dreams — Serum Preset Pack",
    "soundhub://presets/neon-dreams-serum",
    ethers.parseEther("50"), // 50 SND
    1 // Commercial
  );
  await tx.wait();
  console.log(`Seeded listing #1: 'Neon Dreams — Serum Preset Pack' for 50 SND (${tx.hash})`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
