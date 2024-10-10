#!/usr/bin/env python

import asyncio
import click

from postfix_mta_sts_resolver.resolver import STSFetchResult as FR
from postfix_mta_sts_resolver.resolver import STSResolver as Resolver
from tqdm import tqdm


OUTPUT_FILE = "../../mta-sts-hints.txt"
ONE_WEEK_IN_SECONDS = 7*24*60*60


class OrderedFileInserter:
    def __init__(self, filepath):
        self.filepath = filepath
        self.contents = set([])

    def __enter__(self):
        try:
            with open(self.filepath, "r") as f:
                for line in f.readlines():
                    line = line.strip()
                    if line:
                        self.contents.add(line)
        except FileNotFoundError as e:
            # If the file doesn't already exist, start with an empty list
            pass
        return self

    def __exit__(self, *args):
        with open(self.filepath, "w") as f:
            lines = sorted(self.contents)
            for line in lines:
                f.write(line)
                f.write("\n")

    def has(self, item) -> bool:
        # TODO: domain name equality checks / normalization
        return item in self.contents

    def add(self, item):
        self.contents.add(item)


async def do_it(domains_list: click.File):
    resolver = Resolver(loop=None)
    domains = []
    for line in domains_list.readlines():
        domains.append(line.strip())
    results = {}
    with OrderedFileInserter(OUTPUT_FILE) as preload_domains:
        for domain in tqdm(domains):
            if preload_domains.has(domain):
                # No need to check again
                continue
            result, policy = await resolver.resolve(domain)
            if result == FR.VALID:
                max_age = policy[1]['max_age'] 
                mode = policy[1]['mode']
                if mode != 'enforce':
                    results[domain] = f"mode:{mode}"
                    continue
                if max_age < ONE_WEEK_IN_SECONDS:
                    results[domain] = f"max_age:{max_age}"
                    continue

                results[domain] = "including"
                preload_domains.add(domain)

    print("Results:")
    for k, v in results.items():
        print(f"\t{k}\t{v}")


@click.command()
@click.argument("domains_list", type=click.File('r'))
def main(domains_list):
    """
    A bulk import tool
    Check each domain on the user provided list for MTA-STS support
    When MTA-STS support matches requirements, add the domain to the list
    """
    asyncio.run(do_it(domains_list))


if __name__ == "__main__":
    main()
