import { expect } from "chai";
import { ethers, network } from "hardhat";
import { mine, time } from "@nomicfoundation/hardhat-network-helpers";

const ZERO = "0x0000000000000000000000000000000000000000";
const ETHER = 10n ** 18n;

describe("SND token", function () {
  it("mints fixed supply and supports transfers + voting delegation", async function () {
    const [owner, alice] = await ethers.getSigners();
    const SND = await ethers.getContractFactory("SND");
    const snd = await SND.deploy(owner.address, ethers.parseEther("1000000"));

    expect(await snd.totalSupply()).to.equal(ethers.parseEther("1000000"));
    expect(await snd.name()).to.equal("SoundHub Token");
    expect(await snd.symbol()).to.equal("SND");

    await snd.transfer(alice.address, ethers.parseEther("100"));
    expect(await snd.balanceOf(alice.address)).to.equal(ethers.parseEther("100"));

    // delegation enables voting power
    await snd.connect(alice).delegate(alice.address);
    expect(await snd.getVotes(alice.address)).to.equal(ethers.parseEther("100"));
  });
});

describe("SoundHubRelease NFT", function () {
  let snd: any;
  let release: any;
  let alice: any, bob: any, carol: any;

  beforeEach(async function () {
    [alice, bob, carol] = await ethers.getSigners();
    const SND = await ethers.getContractFactory("SND");
    snd = await SND.deploy(alice.address, ethers.parseEther("1000000"));
    const Release = await ethers.getContractFactory("SoundHubRelease");
    release = await Release.deploy();
    await release.setSndToken(await snd.getAddress());
  });

  it("mints a release with royalty and collaborator split", async function () {
    await release.connect(alice).mintRelease(
      "Neon Dreams",
      '{"name":"Neon Dreams","bpm":132}',
      [alice.address, bob.address],
      [7000, 3000],
      500
    );
    expect(await release.ownerOf(1)).to.equal(alice.address);

    const royalty = await release.royaltyInfo(1, 10_000);
    expect(royalty[0]).to.equal(alice.address);
    expect(royalty[1]).to.equal(500); // 5% of 10_000

    const [, metadata, collabs, shares] = await release.releaseOf(1);
    expect(metadata).to.contain("Neon Dreams");
    expect(collabs).to.have.length(2);
    expect(shares[1]).to.equal(3000n);
  });

  it("distributes ETH treasury by split", async function () {
    await release.connect(alice).mintRelease("T1", "{}", [alice.address, bob.address], [7000, 3000], 500);

    await release.connect(carol).fund(1, { value: ETHER });

    await expect(release.connect(alice).claim(1)).to.changeEtherBalance(alice, (ETHER * 7000n) / 10000n);
    await expect(release.connect(bob).claim(1)).to.changeEtherBalance(bob, (ETHER * 3000n) / 10000n);
  });

  it("distributes SND treasury by split and reverts for outsiders", async function () {
    await release.connect(alice).mintRelease("T2", "{}", [alice.address, bob.address], [5000, 5000], 500);

    await snd.transfer(carol.address, ethers.parseEther("200"));
    await snd.connect(carol).approve(await release.getAddress(), ethers.parseEther("200"));
    await release.connect(carol).fundWithSND(1, ethers.parseEther("200"));

    // claim order must not matter: alice first, then bob
    await release.connect(alice).claim(1);
    await release.connect(bob).claim(1);
    // alice deployed SND with 1M supply, paid 200 to carol, then claimed 100
    expect(await snd.balanceOf(alice.address)).to.equal(ethers.parseEther("999900"));
    expect(await snd.balanceOf(bob.address)).to.equal(ethers.parseEther("100"));

    await expect(release.connect(carol).claim(1)).to.be.revertedWithCustomError(release, "NotCollaborator");
  });

  it("rejects invalid splits", async function () {
    await expect(
      release.connect(alice).mintRelease("Bad", "{}", [alice.address, bob.address], [5000, 4000], 500)
    ).to.be.revertedWithCustomError(release, "InvalidSplit");
  });
});

describe("SoundHubGovernor (DAO)", function () {
  it("proposes, votes and executes through the timelock", async function () {
    const [owner, voter1, voter2] = await ethers.getSigners();

    const SND = await ethers.getContractFactory("SND");
    const snd = await SND.deploy(owner.address, ethers.parseEther("1000000"));
    await snd.transfer(voter1.address, ethers.parseEther("400000"));
    await snd.transfer(voter2.address, ethers.parseEther("400000"));
    await snd.connect(voter1).delegate(voter1.address);
    await snd.connect(voter2).delegate(voter2.address);

    const Timelock = await ethers.getContractFactory("TimelockController");
    const timelock = await Timelock.deploy(3600, [owner.address], [owner.address], owner.address);

    const Governor = await ethers.getContractFactory("SoundHubGovernor");
    const gov = await Governor.deploy(await snd.getAddress(), await timelock.getAddress());

    const PROPOSER_ROLE = await timelock.PROPOSER_ROLE();
    const EXECUTOR_ROLE = await timelock.EXECUTOR_ROLE();
    const CANCELLER_ROLE = await timelock.CANCELLER_ROLE();
    await timelock.grantRole(PROPOSER_ROLE, await gov.getAddress());
    await timelock.grantRole(CANCELLER_ROLE, await gov.getAddress());
    await timelock.grantRole(EXECUTOR_ROLE, ZERO); // anyone can execute
    // give the timelock the SND it needs to execute the action
    await snd.transfer(await timelock.getAddress(), ethers.parseEther("100"));

    // propose: transfer 100 SND from owner to voter2
    const calldata = snd.interface.encodeFunctionData("transfer", [voter2.address, ethers.parseEther("100")]);
    const description = "Send 100 SND to voter2";
    const tx = await gov.propose([await snd.getAddress()], [0], [calldata], description);
    const receipt = await tx.wait();
    const parsed = receipt!.logs
      .map((l) => {
        try {
          return gov.interface.parseLog(l);
        } catch {
          return null;
        }
      })
      .find((x) => x && x.name === "ProposalCreated");
    const proposalId = parsed!.args[0];

    // GovernorSettings treats delays as block counts: 1 days = 86400 blocks
    await mine(86401);
    // vote
    await (await gov.connect(voter1).castVote(proposalId, 1)).wait();
    await (await gov.connect(voter2).castVote(proposalId, 1)).wait();

    // advance past voting period (3 days = 259200 blocks)
    await mine(259201);

    const stateAfter = await gov.state(proposalId);
    expect(stateAfter).to.equal(4); // Succeeded

    const descriptionHash = ethers.id(description);
    await (await gov.queue([await snd.getAddress()], [0], [calldata], descriptionHash)).wait();

    // timelock min delay = 3600s
    await time.increase(3601);

    await (await gov.execute([await snd.getAddress()], [0], [calldata], descriptionHash)).wait();
    expect(await snd.balanceOf(voter2.address)).to.equal(ethers.parseEther("400100"));
  });
});
