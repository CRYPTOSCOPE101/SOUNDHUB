import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-network-helpers";

describe("SoundHubFaucet", function () {
  it("claims SND once per cooldown, then again after", async function () {
    const [owner, alice] = await ethers.getSigners();
    const SND = await ethers.getContractFactory("SND");
    const snd = await SND.deploy(owner.address, ethers.parseEther("1000000"));
    const Faucet = await ethers.getContractFactory("SoundHubFaucet");
    const faucet = await Faucet.deploy(await snd.getAddress());

    await snd.transfer(await faucet.getAddress(), ethers.parseEther("5000"));

    await faucet.connect(alice).claim();
    expect(await snd.balanceOf(alice.address)).to.equal(ethers.parseEther("100"));

    // second claim in the same day reverts
    await expect(faucet.connect(alice).claim()).to.be.revertedWithCustomError(faucet, "CooldownNotElapsed");

    await time.increase(2 * 24 * 3600);
    await faucet.connect(alice).claim();
    expect(await snd.balanceOf(alice.address)).to.equal(ethers.parseEther("200"));
  });

  it("reverts when empty and allows owner to pull funds", async function () {
    const [owner] = await ethers.getSigners();
    const SND = await ethers.getContractFactory("SND");
    const snd = await SND.deploy(owner.address, ethers.parseEther("1000000"));
    const Faucet = await ethers.getContractFactory("SoundHubFaucet");
    const faucet = await Faucet.deploy(await snd.getAddress());

    await expect(faucet.connect(owner).claim()).to.be.revertedWithCustomError(faucet, "NotEnoughFunds");

    await snd.transfer(await faucet.getAddress(), ethers.parseEther("10"));
    await faucet.withdraw();
    expect(await snd.balanceOf(owner.address)).to.equal(ethers.parseEther("1000000"));
  });
});
