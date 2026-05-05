# rules/bidders.md - Actors, Groups, and Relations

## Actor Unit

The canonical actor can be an organization, person, group, vehicle, cohort, or
committee. The filing's bidding unit is preserved. A buyer group, club bid,
sponsor/corporate pair, or changing coalition can be one actor and one
estimation unit.

Member relations are composition facts. They do not automatically create
bidder rows, bid events, or estimator rows.

## Relation Direction

- `member_of`: subject is the member; object is the group.
- `joins_group`: subject is the joining actor; object is the group.
- `exits_group`: subject is the exiting actor; object is the group.
- `affiliate_of`: subject is the affiliate; object is the related actor.
- `controls`: subject controls object.
- `acquisition_vehicle_of`: subject is the vehicle; object is parent/group.
- `advises`: subject is advisor; object is advised party.
- `finances`: subject provides financing/capital to object.
- `supports`: subject supports object/transaction.
- `voting_support_for`: subject is supporting holder/entity; object is buyer,
  agreement, proposal, or transaction.
- `rollover_holder_for`: subject is holder rolling/contributing/retaining
  equity; object is buyer, vehicle, surviving company, target, or transaction.

## Group Doctrine

Do not hard-atomize consortiums. A group bid remains a group bid unless the
filing shows a member separately acting as a bidder.

Mac Gray: `CSC/Pamplona` is one group actor when the filing treats
CSC/Pamplona as the bidder. CSC and Pamplona are related actors; Pamplona's
financing/capital role is a relation or judgment, not a second bidder row.

PetSmart: `Buyer Group` is a group actor and bidder unit when the filing uses
that unit. Longview's rollover, membership, or support is dated only when
source-supported and does not atomize the final Buyer Group bid.

Changing coalitions: Sponsor A/E and Sponsor E/G style labels remain separate
actor-cycle facts when the filing treats them differently over time. Do not
make membership permanent without quote support.

## Anonymous and Count-Only Actors

Use `cohort` with `observability=count_only` for generic counts that do not
identify bidder actors. Generic count phrases do not become named bidders.
Anonymous handles are deal-local and must be source-supported.
