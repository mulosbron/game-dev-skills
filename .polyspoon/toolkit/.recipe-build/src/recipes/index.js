import { RecipeRegistry } from './registry.js';
import { lanternRecipe, cottageRecipe, treeRecipe, fenceRecipe, crateRecipe, boulderRecipe } from './builtins.js';
import { benchRecipe } from '../../examples/recipes/bench/index.js';
import { planterRecipe } from '../../examples/recipes/planter/index.js';
import { treasureChestRecipe } from '../../examples/recipes/treasure-chest/index.js';
import { wheelbarrowRecipe } from '../../examples/recipes/wheelbarrow/index.js';
import { stoneWellRecipe } from '../../examples/recipes/stone-well/index.js';
import { coniferRecipe } from '../../examples/recipes/conifer/index.js';
import { rockClusterRecipe } from '../../examples/recipes/rock-cluster/index.js';
import { hydrangeaRecipe } from '../../examples/recipes/hydrangea/index.js';
import { mushroomRecipe } from '../../examples/recipes/mushroom-cluster/index.js';
import { windmillRecipe } from '../../examples/recipes/windmill/index.js';
import { slimeRecipe } from '../../examples/recipes/slime/index.js';
import { rabbitRecipe } from '../../examples/recipes/stylized-rabbit/index.js';
import { humanoidRecipe, foxRecipe } from './rigged.js';
export const registry = new RecipeRegistry();
for (const entry of [lanternRecipe, cottageRecipe, treeRecipe, fenceRecipe, crateRecipe, boulderRecipe, benchRecipe, planterRecipe, treasureChestRecipe, wheelbarrowRecipe, stoneWellRecipe, coniferRecipe, rockClusterRecipe, hydrangeaRecipe, mushroomRecipe, windmillRecipe, slimeRecipe, humanoidRecipe, foxRecipe, rabbitRecipe])
    registry.register(entry);
export const recipe = (id) => registry.get(id);
