from .actor import CompoundActor, FrozenSingleActor, SingleActor
from .parcore import ParameterCore
from epidag.bayesnet.loci import ExoValueLoci
import networkx as nx
from collections import namedtuple

__author__ = 'TimeWz667'


ActorBlueprint = namedtuple('ActorBlueprint', ('Name', 'Type', 'TypeH', 'Flow'))


class SimulationGroup:
    def __init__(self, name, fixed, random, actors, pas):
        self.Name = name
        self.SC = None
        self.Listening = list(pas)
        self.BeFixed = set(fixed)
        self.BeRandom = set(random)
        self.BeActors = set(actors)
        self.FixedChain = None
        self.Children = list()
        self.__actor_blueprints = None

    def set_simulation_core(self, sc):
        self.SC = sc
        bn = sc.BN
        self.FixedChain = [bn[node] for node in bn.sort(self.BeFixed)]

    @property
    def ActorBlueprints(self):
        if not self.__actor_blueprints:
            bps = list()

            bn = self.SC.BN
            g = bn.DAG

            for act in self.BeActors:
                pa = set(g.predecessors(act))
                if pa.intersection(self.BeRandom):
                    flow = set.intersection(nx.ancestors(g, act), self.BeRandom)
                    flow = bn.sort(flow)
                    flow = [bn[nod] for nod in flow]
                    bps.append(ActorBlueprint(act, 'c', 'c', flow))

                elif pa.intersection(self.BeFixed):
                    bps.append(ActorBlueprint(act, 'f', 's', None))
                else:
                    bps.append(ActorBlueprint(act, 'f', 'f', None))

            self.__actor_blueprints = bps

        return self.__actor_blueprints

    def actors(self, pas, hoist=True):
        bn = self.SC.BN
        actors = dict()
        if hoist:
            for act in self.ActorBlueprints:
                name = act.Name
                if act.TypeH == 'c':
                    actor = CompoundActor(name, act.Flow, bn[name])
                elif act.TypeH == 'f':
                    actor = FrozenSingleActor(name, bn[name], pas)
                else:
                    actor = SingleActor(name, bn[name])

                actors[act.Name] = actor
        else:
            for act in self.ActorBlueprints:
                name = act.Name
                if act.Type == 'c':
                    actor = CompoundActor(name, act.Flow, bn[name])
                else:
                    actor = FrozenSingleActor(name, bn[name], pas)

                actors[act.Name] = actor

        return actors

    def generate(self, nickname, exo=None, parent=None, actors=True):
        """
        Generate a simulation core with a nickname
        :param nickname: nickname of the generated core
        :param exo: dict, input exogenous variables
        :param parent: ParameterCore, parent Parameter
        :param actors: bool, true if actors need to be installed locally
        :return:
        """
        pc = ParameterCore(nickname, self, dict(), 0)
        if parent:
            pc.Parent = parent
        exo = exo if exo else dict()

        for k, v in exo.items():
            if k in self.BeFixed:
                pc[k] = v

        prior = 0
        for loci in self.FixedChain:
            if isinstance(loci, ExoValueLoci):
                name = loci.Name
                try:
                    pc[name] = exo[name]
                except KeyError:
                    raise NameError('Exogenous variable {} not found'.format(name))
            else:
                loci.fill(pc)
                prior += loci.evaluate(pc)
        pc.LogPrior = prior
        if actors:
            pc.Actors = self.actors(pc)

        return pc

    def set_response(self, imp, fixed, actors, hoist, pc):
        prior = 0
        for loci in self.FixedChain:
            if loci.Name in imp:
                pc.Locus[loci.Name] = imp[loci.Name]
            elif loci.Name in fixed:
                loci.fill(pc)
            prior += loci.evaluate(pc)

        pc.LogPrior = prior

        bn = self.SC.BN

        for act in actors:
            pc.Actors[act] = FrozenSingleActor(act, bn[act], pc)

        for chd, acts in hoist.items():
            for act in acts:
                pc.ChildrenActors[chd][act] = FrozenSingleActor(act, bn[act], pc)

    def breed(self, nickname, group, pa, exo):
        if group not in self.Children:
            raise KeyError('No matched group')

        ch_sg = self.SC[group]

        hoist = self.SC.Hoist
        chd = ch_sg.generate(nickname, exo=exo, parent=pa, actors=not hoist)

        if hoist:
            if group not in pa.ChildrenActors:
                pa.ChildrenActors[group] = ch_sg.actors(chd)
        else:
            chd.Actors = ch_sg.actors(chd)

        return chd

    def __repr__(self):
        return '{}({}|{}|{})->{}'.format(self.Name,
                                         self.BeFixed if self.BeFixed else '.',
                                         self.BeRandom if self.BeRandom else '.',
                                         self.BeActors if self.BeActors else '.',
                                         self.Children)

    def to_json(self):
        return {
            'Name': self.Name,
            'Listening': list(self.Listening),
            'BeFixed': list(self.BeFixed),
            'BeRandom': list(self.BeRandom),
            'BeActors': list(self.BeActors),
            'Children': [chd.to_json() for chd in self.Children]
        }