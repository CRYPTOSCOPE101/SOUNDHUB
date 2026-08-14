import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

const FAUCET_FUND = ethers.parseEther("5000"); // 5,000 SND for testers

async function main() {
  const network = await ethers.provider.getNetwork();
  const depFile = path.join(__dirname, "..", "deployments", `${network.name}.json`);
  if (!fs.existsSync(depFile)) {
    throw new Error("Run deploy.ts first — deployment file missing");
  }
  const dep = JSON.parse(fs.readFileSync(depFile, "utf8"));

  const [deployer] = await ethers.getSigners();
  console.log(`Deploying from: ${deployer.address}`);
  console.log(`Balance: ${ethers.formatEther(await ethers.provider.getBalance(deployer.address))} ETH\n`);

  // 1. Marketplace (escrow)
  const Market = await ethers.getContractFactory("SoundHubMarket");
  const market = await Market.deploy(dep.snd);
  await market.waitForDeployment();
  const marketAddress = await market.getAddress();
  console.log(`SoundHubMarket:           ${marketAddress}`);

  // 2. Faucet
  const Faucet = await ethers.getContractFactory("SoundHubFaucet");
  const faucet = await Faucet.deploy(dep.snd);
  await faucet.waitForDeployment();
  const faucetAddress = await faucet.getAddress();
  console.log(`SoundHubFaucet:           ${faucetAddress}`);

  // 3. Fund the faucet with SND from the deployer
  const snd = await ethers.getContractAt("SND", dep.snd);
  await (await snd.transfer(faucetAddress, FAUCET_FUND)).wait();
  console.log(`Faucet funded with ${ethers.formatEther(FAUCET_FUND)} SND`);

  // 4. Persist addresses (both backend-facing json and frontend config)
  dep.market = marketAddress;
  dep.faucet = faucetAddress;
  dep.deployedAt = new Date().toISOString();
  fs.writeFileSync(depFile, JSON.stringify(dep, null, 2));

  const feDir = path.join(__dirname, "..", "..", "frontend", "public");
  fs.mkdirSync(feDir, { recursive: true });
  fs.writeFileSync(path.join(feDir, "contracts.json"), JSON.stringify(dep, null, 2));
  console.log(`Saved to ${depFile} and frontend/public/contracts.json`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
