import { expect } from "chai";
import { ethers } from "hardhat";
import { time } from "@nomicfoundation/hardhat-network-helpers";

describe("SoundHubMarket (buy, don't generate)", function () {
  let snd: any;
  let market: any;
  let seller: any, buyer: any, arbiter: any;

  beforeEach(async function () {
    [seller, buyer, arbiter] = await ethers.getSigners();
    const SND = await ethers.getContractFactory("SND");
    snd = await SND.deploy(seller.address, ethers.parseEther("1000000"));
    const Market = await ethers.getContractFactory("SoundHubMarket");
    market = await Market.connect(arbiter).deploy(await snd.getAddress()); // owner = arbiter
    await snd.transfer(buyer.address, ethers.parseEther("1000"));
  });

  it("lists an asset and buys it through escrow with SND", async function () {
    await market.connect(seller).list("Bass Patch Serum", "presets/bass-v2", ethers.parseEther("50"), 1 /* Commercial */);
    const l = await market.listings(1);
    expect(l.name).to.equal("Bass Patch Serum");
    expect(l.price).to.equal(ethers.parseEther("50"));

    await snd.connect(buyer).approve(await market.getAddress(), ethers.parseEther("50"));
    await market.connect(buyer).buy(1);

    // SND is in escrow, seller not paid yet (seller gave 1000 to buyer earlier)
    expect(await snd.balanceOf(await market.getAddress())).to.equal(ethers.parseEther("50"));
    expect(await snd.balanceOf(seller.address)).to.equal(ethers.parseEther("999000"));

    // buyer confirms → seller paid
    await market.connect(buyer).confirmReceipt(1);
    expect(await snd.balanceOf(seller.address)).to.equal(ethers.parseEther("999050"));
    expect(await snd.balanceOf(buyer.address)).to.equal(ethers.parseEther("950"));
  });

  it("seller waits out the dispute window if buyer does not confirm", async function () {
    await market.connect(seller).list("Kick Pack", "kicks/v1", ethers.parseEther("10"), 0);
    await snd.connect(buyer).approve(await market.getAddress(), ethers.parseEther("10"));
    await market.connect(buyer).buy(1);

    await expect(market.connect(seller).withdraw(1)).to.be.revertedWithCustomError(market, "WindowClosed");

    await time.increase(2 * 24 * 3600 + 1);
    await market.connect(seller).withdraw(1);
    expect(await snd.balanceOf(seller.address)).to.equal(ethers.parseEther("999010"));
  });

  it("refund request inside the window returns SND to the buyer", async function () {
    await market.connect(seller).list("Broken Pack", "broken/v1", ethers.parseEther("10"), 0);
    await snd.connect(buyer).approve(await market.getAddress(), ethers.parseEther("10"));
    await market.connect(buyer).buy(1);

    await market.connect(buyer).requestRefund(1);
    await market.connect(arbiter).resolveRefund(1, true);

    expect(await snd.balanceOf(buyer.address)).to.equal(ethers.parseEther("1000"));
    expect(await snd.balanceOf(await market.getAddress())).to.equal(0);
  });

  it("rejects double sales and non-seller delists", async function () {
    await market.connect(seller).list("One Shot", "oneshot/v1", ethers.parseEther("5"), 0);
    await snd.connect(buyer).approve(await market.getAddress(), ethers.parseEther("5"));
    await market.connect(buyer).buy(1);
    await expect(market.connect(buyer).buy(1)).to.be.revertedWithCustomError(market, "AlreadySold");
    await expect(market.connect(buyer).delist(1)).to.be.revertedWithCustomError(market, "NotSeller");
  });
});
