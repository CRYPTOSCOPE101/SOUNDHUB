import { ethers } from "hardhat";
import * as fs from "fs";
import * as path from "path";

async function main() {
  const depFile = path.join(__dirname, "..", "deployments", "baseSepolia.json");
  const dep = JSON.parse(fs.readFileSync(depFile, "utf8"));

  const [deployer] = await ethers.getSigners();
  const release = await ethers.getContractAt("SoundHubRelease", dep.release);

  const USER_WALLET = process.env.DEMO_COLLABORATOR || "0xbFB5C354f091d200C75E43BF24562858d3aF4b39";
  const tx = await release.mintRelease(
    "Neon Dreams",
    '{"name":"Neon Dreams","platform":"soundhub","bpm":132}',
    [deployer.address, USER_WALLET],
    [7000, 3000],
    500 // 5% royalty
  );
  const receipt = await tx.wait();
  const parsed = receipt!.logs
    .map((l) => {
      try {
        return release.interface.parseLog(l);
      } catch {
        return null;
      }
    })
    .find((x) => x && x.name === "ReleaseMinted");
  const tokenId = parsed ? Number(parsed.args[0]) : 1;
  console.log(JSON.stringify({ tokenId, contract: dep.release, txHash: tx.hash }));
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
