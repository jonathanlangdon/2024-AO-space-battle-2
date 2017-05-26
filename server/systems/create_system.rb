class CreateSystem

  def update(entity_manager, dt, input, res)
    map_info = entity_manager.first(MapInfo).get(MapInfo)

    entity_manager.each_entity(CreateCommand, Base, Unit, Position, Label, PlayerOwned) do |base_ent|
      cmd, base, u, base_pos, label, owner = base_ent.components

      cmd.build_time -= 1
      if cmd.build_time == 0
        cost = RtsGame::UNITS[cmd.type][:cost]
        if base.resource >= cost
          base.resource -= cost
          label.text = base.resource
          Prefab.unit(type: cmd.type, entity_manager: entity_manager, map_info: map_info,
                      x: base_pos.x, y: base_pos.y, player_id: owner.id)
          u.dirty = true
        else
          puts "#{owner.id} tried to create #{cmd.type} without enough resources #{cost} required, but only has #{base.resource}"
        end

        u.status = :idle
        entity_manager.remove_component(klass: CreateCommand, id: base_ent.id)
      else
        if u.status != :building
          u.dirty = true 
          u.status = :building
        end
      end
    end
  end
end

