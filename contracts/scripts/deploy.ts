import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

const ZERO = "0x0000000000000000000000000000000000000000";
const SND_SUPPLY = ethers.parseEther("1000000"); // 1,000,000 SND
const TIMELOCK_DELAY = 86400; // 1 day

async function main() {
  const [deployer] = await ethers.getSigners();
  console.log(`Deploying from: ${deployer.address}`);
  console.log(`Balance: ${ethers.formatEther(await ethers.provider.getBalance(deployer.address))} ETH\n`);

  // 1. SND token (ERC-20Votes + Permit)
  const SND = await ethers.getContractFactory("SND");
  const snd = await SND.deploy(deployer.address, SND_SUPPLY);
  await snd.waitForDeployment();
  const sndAddress = await snd.getAddress();
  console.log(`SND (ERC-20):            ${sndAddress}`);

  // 2. Release NFT (ERC-721 + ERC-2981 + splits)
  const Release = await ethers.getContractFactory("SoundHubRelease");
  const release = await Release.deploy();
  await release.waitForDeployment();
  const releaseAddress = await release.getAddress();
  await (await release.setSndToken(sndAddress)).wait();
  console.log(`SoundHubRelease (NFT):   ${releaseAddress}`);

  // 3. Timelock
  const Timelock = await ethers.getContractFactory("TimelockController");
  const timelock = await Timelock.deploy(TIMELOCK_DELAY, [deployer.address], [deployer.address], deployer.address);
  await timelock.waitForDeployment();
  const timelockAddress = await timelock.getAddress();
  console.log(`Timelock:                ${timelockAddress}`);

  // 4. Governor (DAO)
  const Governor = await ethers.getContractFactory("SoundHubGovernor");
  const governor = await Governor.deploy(sndAddress, timelockAddress);
  await governor.waitForDeployment();
  const governorAddress = await governor.getAddress();
  console.log(`SoundHubGovernor (DAO):  ${governorAddress}`);

  // 5. Wire roles
  const PROPOSER_ROLE = await timelock.PROPOSER_ROLE();
  const CANCELLER_ROLE = await timelock.CANCELLER_ROLE();
  const EXECUTOR_ROLE = await timelock.EXECUTOR_ROLE();
  await (await timelock.grantRole(PROPOSER_ROLE, governorAddress)).wait();
  await (await timelock.grantRole(CANCELLER_ROLE, governorAddress)).wait();
  await (await timelock.grantRole(EXECUTOR_ROLE, ZERO)).wait(); // anyone may execute
  console.log("Timelock roles wired: PROPOSER/CANCELLER -> governor, EXECUTOR -> anyone");

  // 6. Persist addresses
  const network = await ethers.provider.getNetwork();
  const out = {
    network: network.name,
    chainId: Number(network.chainId),
    deployer: deployer.address,
    snd: sndAddress,
    release: releaseAddress,
    timelock: timelockAddress,
    governor: governorAddress,
    deployedAt: new Date().toISOString(),
  };
  const dir = path.join(__dirname, "..", "deployments");
  fs.mkdirSync(dir, { recursive: true });
  const file = path.join(dir, `${network.name}.json`);
  fs.writeFileSync(file, JSON.stringify(out, null, 2));
  console.log(`\nSaved deployment addresses to ${file}`);

  // also publish to the frontend so the UI can talk to the contracts
  const feDir = path.join(__dirname, "..", "..", "frontend", "public");
  fs.mkdirSync(feDir, { recursive: true });
  fs.writeFileSync(path.join(feDir, "contracts.json"), JSON.stringify(out, null, 2));
  console.log(`Copied to ${path.join("frontend", "public", "contracts.json")}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
